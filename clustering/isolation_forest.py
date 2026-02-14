from sklearn.ensemble import IsolationForest

iso = IsolationForest(contamination=0.05) # proportion of the dataset expected to be anomalies; lower means stricter (only extreme outliers are flagged) → less false positives, more false negatives, higher means looser (more data flagged as sensitive) → more false positives, less false negatives
iso.fit(public_embeddings)
