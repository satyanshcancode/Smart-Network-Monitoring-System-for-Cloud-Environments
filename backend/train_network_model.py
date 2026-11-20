import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import classification_report, confusion_matrix
from xgboost import XGBClassifier
import joblib
import warnings

warnings.filterwarnings("ignore")

import os

# Get the directory where THIS script is located
script_dir = os.path.dirname(os.path.abspath(__file__))

# Build the full path to the CSV file
csv_path = os.path.join(script_dir, "network_telemetry_dataset.csv")

# Now read from the correct path
df = pd.read_csv(csv_path)

def engineer_features(data):
    df_feat = data.copy()
    df_feat["latency_cv"] = df_feat["std_latency"] / df_feat["avg_latency"]
    df_feat["tail_spread"] = df_feat["p99_latency"] - df_feat["p95_latency"]
    df_feat["error_index"] = df_feat["failure_rate"] + df_feat["timeout_rate"] * 2
    df_feat["efficiency"] = df_feat["throughput_bytes_per_sec"] / (df_feat["request_velocity"] + 1)
    df_feat["health_score"] = (
        (1 / (df_feat["avg_latency"] + 1)) * 100
        + (1 - df_feat["failure_rate"]) * 100
        + (df_feat["request_velocity"] / 5) * 100
    ) / 3
    return df_feat

df = engineer_features(df)

X = df.drop("label", axis=1)
y = df["label"]

le = LabelEncoder()
y_encoded = le.fit_transform(y)

X_train, X_test, y_train, y_test = train_test_split(
    X, y_encoded, test_size=0.2, random_state=42, stratify=y_encoded
)

scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

models = {
    "RandomForest": RandomForestClassifier(
        n_estimators=200,
        max_depth=10,
        min_samples_split=5,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    ),
    "GradientBoosting": GradientBoostingClassifier(
        n_estimators=150,
        learning_rate=0.1,
        max_depth=6,
        random_state=42,
    ),
    "XGBoost": XGBClassifier(
        n_estimators=200,
        learning_rate=0.05,
        max_depth=6,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        eval_metric="mlogloss",
    ),
}

results = {}

for name, model in models.items():
    cv_scores = cross_val_score(
        model,
        X_train_scaled,
        y_train,
        cv=StratifiedKFold(n_splits=5, shuffle=True, random_state=42),
        scoring="f1_weighted",
    )

    model.fit(X_train_scaled, y_train)
    y_pred = model.predict(X_test_scaled)

    report = classification_report(y_test, y_pred, output_dict=True)

    results[name] = {
        "cv_f1_mean": cv_scores.mean(),
        "cv_f1_std": cv_scores.std(),
        "test_accuracy": report["accuracy"],
        "test_f1": report["weighted avg"]["f1-score"],
        "model": model,
    }

best_model_name = max(results, key=lambda x: results[x]["test_f1"])
best_model = results[best_model_name]["model"]

y_pred_best = best_model.predict(X_test_scaled)

print("Best Model:", best_model_name)
print(classification_report(y_test, y_pred_best))

cm = confusion_matrix(y_test, y_pred_best)
print(cm)

if hasattr(best_model, "feature_importances_"):
    importance_df = pd.DataFrame(
        {"feature": X.columns, "importance": best_model.feature_importances_}
    ).sort_values("importance", ascending=False)

    print(importance_df.head(10))

joblib.dump(best_model, "network_model.pkl")
joblib.dump(scaler, "scaler.pkl")
joblib.dump(le, "label_encoder.pkl")
joblib.dump(X.columns.tolist(), "feature_names.pkl")

print("Saved: network_model.pkl, scaler.pkl, label_encoder.pkl, feature_names.pkl")