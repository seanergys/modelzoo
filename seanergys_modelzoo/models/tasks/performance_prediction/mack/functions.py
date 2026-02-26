import numpy as np 
from sklearn.cluster import KMeans
from sentence_transformers import SentenceTransformer

def fit_transform_kmeans(flops: np.ndarray, memory_bw: np.ndarray, k_flops: int, k_memory_bw: int) -> list:
    """
    Fit KMeans on flops and memory bandwidth arrays separately,
    order labels by ascending centroid values, and return combined labels.
    
    Args:
        flops: Array of FLOP values
        memory_bw: Array of memory bandwidth values
        k_flops: Number of clusters for flops KMeans
        k_memory_bw: Number of clusters for memory bandwidth KMeans
    
    Returns:
        List of tuples combining flops and memory bandwidth labels
    """
    def fit_and_reorder(data: np.ndarray, k: int) -> np.ndarray:
        kmeans = KMeans(n_clusters=k)
        labels = kmeans.fit_predict(data.reshape(-1, 1))
        centroids = kmeans.cluster_centers_.flatten()

        sorted_centroid_indices = np.argsort(centroids)
        label_mapping = np.empty_like(sorted_centroid_indices)
        label_mapping[sorted_centroid_indices] = np.arange(k)

        return label_mapping[labels]

    flops_labels = fit_and_reorder(flops, k_flops)
    memory_bw_labels = fit_and_reorder(memory_bw, k_memory_bw)

    combined_labels = list(zip(flops_labels.tolist(), memory_bw_labels.tolist()))
    return combined_labels

def transform_pclass(kmeans_flops:KMeans, kmeans_memory_bw:KMeans, flops: np.ndarray, memory_bw: np.ndarray) -> list:
    """
    Transform flops and memory bandwidth arrays using pre-fitted KMeans models,
    order labels by ascending centroid values, and return combined labels.

    Args:
        kmeans_flops: KMeans trained on flops values
        kmeans_memory_bw: KMeans trained on memory bandwidth values
        flops: Array of FLOP values
        memory_bw: Array of memory bandwidth values

    Returns:
        List of tuples combining flops and memory bandwidth labels
    """
    def predict_and_reorder(kmeans: KMeans, data: np.ndarray) -> np.ndarray:
        labels = kmeans.predict(data.reshape(-1, 1))
        centroids = kmeans.cluster_centers_.flatten()

        sorted_centroid_indices = np.argsort(centroids)
        label_mapping = np.empty_like(sorted_centroid_indices)
        label_mapping[sorted_centroid_indices] = np.arange(len(centroids))

        return label_mapping[labels]

    flops_labels = predict_and_reorder(kmeans_flops, flops)
    memory_bw_labels = predict_and_reorder(kmeans_memory_bw, memory_bw)

    combined_labels = list(zip(flops_labels.tolist(), memory_bw_labels.tolist()))
    return combined_labels

def parse_job_data(script:str):
    out = ""
    for e in script.split("\n"):
        if (e.startswith("#")) or (e == "\n") or (e == " "):
            continue 
        idx = -1
        if "#" in e:
            idx = e.index("#")
        out += e[:idx].replace("\n", "")
    return out

def transform_embeddings(features: np.ndarray, encoder_weights:str = "google/embeddinggemma-300m") -> np.ndarray:
    """
    Concatenate feature values into strings and encode with SentenceTransformer.

    Args:
        features: 2D array of shape (n_samples, n_features)
        encoder_weights: str containing the name of the encoder's weights, defaults to google/embeddinggemma-300m

    Returns:
        Embedding array of shape (n_samples, embedding_dim)
    """
    encoder = SentenceTransformer(encoder_weights)
    sentences = [" ".join(str(val) for val in row) for row in features]
    return encoder.encode(sentences)

def embedding_parsing(embedding):
    arr = np.zeros((384,))
    arr[:] = np.array(embedding[0])
    return arr