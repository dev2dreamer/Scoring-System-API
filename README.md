## Architechure
![mermaid-diagram-2025-02-22-194520](https://github.com/user-attachments/assets/97431c49-e22a-4b2f-9f95-a01a9004d80c)



## Installation

1. **Clone the Repository:**


2. **Create a Virtual Environment and Activate It:**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. **Install Dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

   **Required Dependencies:**
   - fastapi
   - uvicorn
   - pymongo
   - pandas
   - numpy
   - fuzzywuzzy
   - jellyfish
   - scipy

4. **Set Up MongoDB:**

   Ensure you have a running MongoDB instance. The default connection URI is `mongodb://localhost:27017/`. Adjust the URI in the code if needed.

## Data Ingestion

   This script uses the `FoodDataProcessor` class to load data from the CSV files and store them into respective collections (`nutrition`, `recipes`, `carbon_footprint`, and `interactions`).

## API Endpoints

The API is built using FastAPI. Key endpoints include:

- **Health Check:**
  
  ```
  GET /health
  ```
  
  Returns a simple status check.

- **Score Calculation:**
  
  ```
  POST /score
  ```
  
  **Request Body:**
  
  ```json
  {
      "dish_name": "Paneer Butter Masala",
      "user_context": {
          "medications": ["Warfarin"],
          "conditions": ["Hypertension"]
      }
  }
  ```

  **Response:**
  
  ```json
  {
      "dish_name": "Paneer Butter Masala",
      "unified_score": 85.0,
      "score_components": {
          "health": 90.0,
          "carbon": 65.0,
          "interactions": 70.0
      },
      "confidence_interval": 87.5,
      "explanation": {
          "health_breakdown": "ICMR-aligned nutrient balance",
          "carbon_factors": "MP-adjusted CO2e values",
          "interaction_risks": "Drug-food interaction hierarchy"
      },
      "alternatives": [{"name": "Suggested Alternative", "score": 85}]
  }
  ```

## Usage

1. **Start the API Server:**

   ```bash
   uvicorn api:app --host 0.0.0.0 --port 8000
   ```

2. **Access the Documentation:**

   Open your browser and navigate to `http://localhost:8000/docs` to view the interactive API documentation provided by Swagger UI.

3. **Testing:**

   Use any API client (like Postman) or the built-in Swagger UI to test the endpoints.

## Future Enhancements

- **ML Ensemble Integration:** Enhance scoring by training ensemble models (Random Forest and XGBoost) on aggregated ingredient features.
- **Improved Confidence Metrics:** Develop more robust measures for data completeness and reliability.
- **Interactive Dashboard:** Build a frontend UI for visualizing scores and recommendations.
- **Expanded Dataset Support:** Integrate additional regional datasets for broader coverage.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
