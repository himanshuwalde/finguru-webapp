import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import make_pipeline
from sklearn.metrics import accuracy_score, classification_report
import joblib

print("🧪 Starting the AI Training Laboratory...")

# --- 1. LOAD THE DATA ---
try:
    # Read the Kaggle CSV file
    df = pd.read_csv('transactions_dataset.csv')
    print(f"✅ Loaded dataset with {len(df)} transactions.")
except FileNotFoundError:
    print("❌ ERROR: Could not find 'transactions_dataset.csv'. Please make sure it's in the same folder!")
    exit()

# --- 2. PREPROCESS & CLEAN ---
# Drop any rows that have blank descriptions or categories
df = df.dropna(subset=['description', 'category'])

# Standardize the text (convert everything to lowercase so "Uber" and "UBER" are treated the same)
X = df['description'].str.lower() 
y = df['category']

# --- 3. SPLIT THE DATA ---
# We keep 80% of the data for training, and hide 20% to test the AI like a final exam.
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
print("✅ Data cleaned and split into training and testing sets.")

# --- 4. BUILD THE AI PIPELINE ---
# stop_words='english' removes useless words like "the", "and", "at" from the descriptions
print("🧠 Training the model (this might take a few seconds)...")
model = make_pipeline(TfidfVectorizer(stop_words='english'), MultinomialNB())

# Teach the AI!
model.fit(X_train, y_train)

# --- 5. TEST THE AI ---
# Ask the AI to predict the categories for the 20% of data it has never seen
predictions = model.predict(X_test)

# Grade the exam
score = accuracy_score(y_test, predictions)
print(f"🎯 AI Accuracy Score: {score * 100:.2f}%")

# --- 6. FREEZE AND EXPORT ---
# Save the fully trained brain into a tiny file
joblib.dump(model, 'expense_model.pkl')
print("📦 SUCCESS! The model has been frozen and saved as 'expense_model.pkl'.")