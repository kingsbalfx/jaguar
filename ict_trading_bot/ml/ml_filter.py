def ml_quality_filter(features, model, threshold=0.65):
    """
    model: trained XGBoost model
    """
    if model is None:
        return True, 1.0  # allow trades if ML disabled

    probability = model.predict_proba([features])[0][1]
    return probability >= threshold, probability
