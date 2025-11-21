import numpy as np
import torch
from laion_clap import CLAP_Module
from pymilvus import connections, Collection, CollectionSchema, FieldSchema, DataType, utility
import librosa
import os

class VectorFingerprinter:
    """
    Audio fingerprinting using CLAP (Contrastive Language-Audio Pretraining) embeddings
    and Milvus vector database for similarity search
    """

    def __init__(self, sample_rate=48000, milvus_host='milvus', milvus_port='19530'):
        self.sample_rate = sample_rate
        self.milvus_host = milvus_host
        self.milvus_port = milvus_port
        self.collection_name = "audio_fingerprints"

        # Initialize CLAP model
        print("Loading CLAP model...")
        self.clap_model = CLAP_Module(enable_fusion=False, amodel='HTSAT-tiny')
        self.clap_model.load_ckpt()  # Load pretrained weights

        # Connect to Milvus
        self._connect_milvus()
        self._create_collection()

    def _connect_milvus(self):
        """Connect to Milvus vector database"""
        try:
            connections.connect(
                alias="default",
                host=self.milvus_host,
                port=self.milvus_port
            )
            print(f"Connected to Milvus at {self.milvus_host}:{self.milvus_port}")
        except Exception as e:
            print(f"Warning: Could not connect to Milvus: {e}")
            print("Vector search features will be disabled")

    def _create_collection(self):
        """Create Milvus collection for storing audio embeddings"""
        try:
            # Check if collection exists
            if utility.has_collection(self.collection_name):
                self.collection = Collection(self.collection_name)
                print(f"Using existing collection: {self.collection_name}")
                return

            # Define schema
            fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="fingerprint_id", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="segment_index", dtype=DataType.INT64),
                FieldSchema(name="start_time", dtype=DataType.FLOAT),
                FieldSchema(name="end_time", dtype=DataType.FLOAT),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=512)  # CLAP embedding dimension
            ]

            schema = CollectionSchema(fields=fields, description="Audio fingerprint embeddings")

            # Create collection
            self.collection = Collection(name=self.collection_name, schema=schema)

            # Create index for vector search
            index_params = {
                "metric_type": "L2",  # Euclidean distance
                "index_type": "IVF_FLAT",
                "params": {"nlist": 128}
            }
            self.collection.create_index(field_name="embedding", index_params=index_params)

            print(f"Created new collection: {self.collection_name}")
        except Exception as e:
            print(f"Warning: Could not create Milvus collection: {e}")
            self.collection = None

    def generate_embedding(self, audio_data):
        """
        Generate CLAP embedding for audio data
        Returns: 512-dimensional embedding vector
        """
        try:
            # CLAP expects audio at 48kHz
            if self.sample_rate != 48000:
                audio_data = librosa.resample(audio_data, orig_sr=self.sample_rate, target_sr=48000)

            # Ensure audio is the right shape
            if len(audio_data.shape) == 1:
                audio_data = audio_data[np.newaxis, :]  # Add batch dimension

            # Convert to tensor
            audio_tensor = torch.from_numpy(audio_data).float()

            # Generate embedding
            with torch.no_grad():
                embedding = self.clap_model.get_audio_embedding_from_data(
                    x=audio_tensor,
                    use_tensor=True
                )

            # Convert to numpy and normalize
            embedding = embedding.cpu().numpy().flatten()
            embedding = embedding / (np.linalg.norm(embedding) + 1e-10)

            return embedding.tolist()

        except Exception as e:
            print(f"Error generating embedding: {e}")
            return None

    def generate_segment_embeddings(self, audio_data, segment_duration=10.0):
        """
        Generate embeddings for audio segments
        Uses longer segments (10s) for better context
        """
        samples_per_segment = int(segment_duration * self.sample_rate)
        segments = []

        for i in range(0, len(audio_data), samples_per_segment):
            segment_data = audio_data[i:i + samples_per_segment]

            # Skip very short segments
            if len(segment_data) < samples_per_segment * 0.3:
                continue

            # Pad if necessary
            if len(segment_data) < samples_per_segment:
                segment_data = np.pad(segment_data, (0, samples_per_segment - len(segment_data)))

            embedding = self.generate_embedding(segment_data)

            if embedding:
                segments.append({
                    'startTime': i / self.sample_rate,
                    'endTime': min((i + samples_per_segment) / self.sample_rate, len(audio_data) / self.sample_rate),
                    'embedding': embedding,
                    'duration': len(segment_data) / self.sample_rate
                })

        return segments

    def store_embeddings(self, fingerprint_id, segments):
        """Store segment embeddings in Milvus"""
        if not self.collection:
            print("Milvus collection not available")
            return False

        try:
            # Prepare data for insertion
            data = [
                [fingerprint_id] * len(segments),  # fingerprint_id
                list(range(len(segments))),  # segment_index
                [seg['startTime'] for seg in segments],  # start_time
                [seg['endTime'] for seg in segments],  # end_time
                [seg['embedding'] for seg in segments]  # embedding
            ]

            # Insert into Milvus
            self.collection.insert(data)
            self.collection.flush()

            print(f"Stored {len(segments)} embeddings for fingerprint {fingerprint_id}")
            return True

        except Exception as e:
            print(f"Error storing embeddings: {e}")
            return False

    def search_similar(self, query_embedding, top_k=10, threshold=0.8):
        """
        Search for similar audio segments using vector similarity
        Returns segments with similarity above threshold
        """
        if not self.collection:
            print("Milvus collection not available")
            return []

        try:
            # Load collection to memory
            self.collection.load()

            # Search parameters
            search_params = {
                "metric_type": "L2",
                "params": {"nprobe": 10}
            }

            # Perform search
            results = self.collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                output_fields=["fingerprint_id", "segment_index", "start_time", "end_time"]
            )

            # Convert L2 distance to similarity score (0-1 range)
            # Lower L2 distance = higher similarity
            matches = []
            for hits in results:
                for hit in hits:
                    # Convert L2 distance to similarity
                    # L2 distance for normalized vectors ranges from 0 to 2
                    # Similarity = 1 - (L2_dist / 2)
                    similarity = 1 - (hit.distance / 2)

                    if similarity >= threshold:
                        matches.append({
                            'fingerprint_id': hit.entity.get('fingerprint_id'),
                            'segment_index': hit.entity.get('segment_index'),
                            'start_time': hit.entity.get('start_time'),
                            'end_time': hit.entity.get('end_time'),
                            'similarity': similarity,
                            'distance': hit.distance
                        })

            return matches

        except Exception as e:
            print(f"Error searching embeddings: {e}")
            return []

    def verify_audio(self, query_segments, stored_fingerprint_id):
        """
        Verify audio by comparing embeddings of query segments
        against stored embeddings
        """
        if not self.collection:
            return {
                'matched': False,
                'error': 'Milvus collection not available'
            }

        all_matches = []
        matched_segments = 0

        for i, query_seg in enumerate(query_segments):
            matches = self.search_similar(
                query_seg['embedding'],
                top_k=5,
                threshold=0.85
            )

            # Check if any match is from the stored fingerprint
            segment_matched = False
            for match in matches:
                if match['fingerprint_id'] == stored_fingerprint_id:
                    segment_matched = True
                    all_matches.append({
                        'query_segment': i,
                        'query_time': f"{query_seg['startTime']:.2f}s - {query_seg['endTime']:.2f}s",
                        'matched_segment': match['segment_index'],
                        'matched_time': f"{match['start_time']:.2f}s - {match['end_time']:.2f}s",
                        'similarity': match['similarity']
                    })
                    break

            if segment_matched:
                matched_segments += 1

        # Calculate overall match percentage
        match_percentage = (matched_segments / len(query_segments)) * 100 if query_segments else 0

        return {
            'matched': match_percentage >= 70,  # 70% threshold for overall match
            'match_percentage': match_percentage,
            'matched_segments': matched_segments,
            'total_segments': len(query_segments),
            'segment_matches': all_matches,
            'is_partial_match': 30 <= match_percentage < 70,
            'is_tampered': match_percentage < 30
        }

    def delete_embeddings(self, fingerprint_id):
        """Delete embeddings for a fingerprint from Milvus"""
        if not self.collection:
            return False

        try:
            expr = f'fingerprint_id == "{fingerprint_id}"'
            self.collection.delete(expr)
            self.collection.flush()
            print(f"Deleted embeddings for fingerprint {fingerprint_id}")
            return True
        except Exception as e:
            print(f"Error deleting embeddings: {e}")
            return False
