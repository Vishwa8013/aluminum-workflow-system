import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
import joblib

# Simulated dataset for aluminum extraction
np.random.seed(42)
n = 2500
data = pd.DataFrame({
    "bauxite_mass": np.random.uniform(100, 500, n),
    "caustic_soda_conc": np.random.uniform(30, 60, n),
    "temperature": np.random.uniform(700, 900, n),
    "pressure": np.random.uniform(1, 10, n),
    "reaction_time": np.random.uniform(3, 7, n),
    "purity_factor": np.random.uniform(0.7, 1.0, n)
})

# yield roughly increases with purity, temperature and caustic concentration
data["yield_kg"] = (
    0.02 * data["bauxite_mass"]
    + 0.3 * data["caustic_soda_conc"]
    + 0.05 * (data["temperature"] - 700)
    + 0.5 * np.exp(-((data["reaction_time"] - 5)**2)/2)
    + 5 * data["purity_factor"]
    - 0.2 * data["pressure"]
    + np.random.normal(0, 10, n)
)

X = data[["bauxite_mass", "caustic_soda_conc", "temperature", "pressure", "reaction_time", "purity_factor"]]
y = data["yield_kg"]

model = RandomForestRegressor(n_estimators=200, random_state=42)
model.fit(X, y)

joblib.dump(model, "aluminumRec/aluminum_yield_model.pkl")
print("✅ Aluminum yield model trained and saved successfully.")
