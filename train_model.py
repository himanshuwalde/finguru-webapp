import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_absolute_error, r2_score
import joblib
import re

print("🚀 Starting Upgraded Healthcare Model Training...")

# 1. LOAD THE DATA
df = pd.read_csv('indian_health_insurance_claims_dataset.csv')

# 2. CLEANING FINANCIAL DATA
if df['total_claim_amount'].dtype == 'object':
    df['total_claim_amount'] = df['total_claim_amount'].apply(lambda x: float(re.sub(r'[^\d.]', '', str(x))))

# 3. ENCODING CATEGORICAL DATA
label_encoders = {}
categorical_columns = ['gender', 'hospital_tier', 'has_diabetes', 'has_hypertension', 'tobacco_usage']

for col in categorical_columns:
    df[col] = df[col].fillna(df[col].mode()[0]) 
    le = LabelEncoder()
    df[col] = le.fit_transform(df[col].astype(str))
    label_encoders[col] = le

df['age'] = df['age'].fillna(df['age'].median())

# 🌟 NEW: FEATURE ENGINEERING
# Create a "Total Risk Score" combining the health flags
df['total_risk_factors'] = df['has_diabetes'] + df['has_hypertension'] + df['tobacco_usage']

# 4. FEATURE SELECTION
features = ['age', 'gender', 'hospital_tier', 'has_diabetes', 'has_hypertension', 'tobacco_usage', 'total_risk_factors']
X = df[features].copy()

# 🌟 NEW: LOG TRANSFORMATION
# Compress the massive outliers so the model can learn the baseline easily
y = np.log1p(df['total_claim_amount'])

# 5. TRAIN-TEST SPLIT
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# 🌟 NEW: HYPERPARAMETER TUNING
print("🧠 Training Tuned Random Forest Regressor...")
model = RandomForestRegressor(
    n_estimators=300,        # More trees for better consensus
    max_depth=None,          # Let the trees grow deeper to find complex patterns
    min_samples_split=10,    # Prevent overfitting by requiring enough data to split
    min_samples_leaf=4,      # Ensure ending leaves aren't just memorizing single patients
    random_state=42,
    n_jobs=-1                # Use all CPU cores for speed
)
model.fit(X_train, y_train)

# 6. EVALUATION
# Make predictions in Log space, then reverse them (expm1) back to normal Rupees
log_predictions = model.predict(X_test)
real_predictions = np.expm1(log_predictions)
y_test_real = np.expm1(y_test)

mae = mean_absolute_error(y_test_real, real_predictions)
r2 = r2_score(y_test_real, real_predictions)

print(f"📊 Upgraded Model Performance:")
print(f" - Mean Error: ₹{mae:,.2f}")
print(f" - Accuracy (R-Squared): {r2:.2f}")

# 7. SAVE THE MODEL
export_data = {
    'model': model,
    'encoders': label_encoders,
    'features': features
}
joblib.dump(export_data, 'indian_healthcare_model.joblib')
print("✅ Upgraded Model saved successfully!")