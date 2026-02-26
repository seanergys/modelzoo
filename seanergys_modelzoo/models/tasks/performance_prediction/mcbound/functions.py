import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.preprocessing import LabelEncoder

def transform_embeddings(features: np.ndarray, encoder_weights:str = "all-MiniLM-L6-v2") -> np.ndarray:
    """
    Concatenate feature values into strings and encode with SentenceTransformer.

    Args:
        features: 2D array of shape (n_samples, n_features)
        encoder_weights: str containing the name of the encoder's weights, defaults to all-MiniLM-L6-v2

    Returns:
        Embedding array of shape (n_samples, embedding_dim)
    """
    encoder = SentenceTransformer(encoder_weights)
    sentences = [" ".join(str(val) for val in row) for row in features]
    return encoder.encode(sentences)

def fit_categorical(features: np.ndarray) -> None:
    """
    Fit a LabelEncoder for each feature column in the 2D array.

    Args:
        features: 2D array of shape (n_samples, n_features)
    """
    label_encoders = [LabelEncoder() for _ in range(features.shape[1])]
    for i, le in enumerate(label_encoders):
        le.fit(features[:, i])
    return label_encoders


def fit_transform_categorical(features: np.ndarray) -> np.ndarray:
    """
    Fit a LabelEncoder for each feature column and transform the data.

    Args:
        features: 2D array of shape (n_samples, n_features)

    Returns:
        Encoded 2D array of shape (n_samples, n_features)
    """
    label_encoders = fit_categorical(features)
    return transform_categorical(label_encoders=label_encoders, features=features)
    


def transform_categorical(label_encoders:LabelEncoder, features: np.ndarray) -> np.ndarray:
    """
    Transform feature columns using the fitted LabelEncoders.

    Args:
        label_encoders: The trained instance of the LabelEncoder
        features: 2D array of shape (n_samples, n_features)

    Returns:
        Encoded 2D array of shape (n_samples, n_features)
    """
    return np.column_stack([
        le.transform(features[:, i])
        for i, le in enumerate(label_encoders)
    ])

def embedding_parsing(embedding):
    arr = np.zeros((384,))
    arr[:] = np.array(embedding[0])
    return arr