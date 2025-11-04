import joblib
import numpy as np
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
model_path = os.path.join(BASE_DIR, "aluminum_yield_model.pkl")

if not os.path.exists(model_path):
    model = None
else:
    model = joblib.load(model_path)


def predict_yield(bauxite_mass, caustic_soda_conc, temperature, pressure, purity, reaction_time):
    """
    Predict aluminum yield and byproduct using the trained model.
    """
    if model is None:
        return {"error": "Model file missing. Train the model first."}

    try:
        features = np.array([[bauxite_mass, caustic_soda_conc, temperature, pressure, purity, reaction_time]])
        prediction = model.predict(features)[0]

        # Simple derived estimate for byproduct amount
        byproduct = round(prediction * 0.52, 2)

        return {
            "predicted_yield": float(prediction),
            "predicted_byproduct": byproduct
        }

    except Exception as e:
        return {"error": str(e)}
