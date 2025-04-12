from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import Dict, Optional, List, Any
from Scoring import FoodScorer  # This uses MongoDB Atlas with connection string: mongodb+srv://p:zMtpS9kUGUwKmppe@mydbcluster.8axgt8u.mongodb.net/
import uvicorn
import logging
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
import numpy as np
import json
import traceback
import re

# Hard-coded port number
PORT = 8765

app = FastAPI(
    title="Aahar Food Intelligence API",
    description="Unified scoring system for Indian food nutritional safety",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("aahar-api")

class UserContext(BaseModel):
    medications: Optional[List[str]] = []
    conditions: Optional[List[str]] = []

class ScoreRequest(BaseModel):
    dish_name: str
    user_context: Optional[Dict[str, Any]] = None

class ScoreResponse(BaseModel):
    dish_name: str
    unified_score: float
    score_components: Dict[str, float]
    confidence_interval: float
    explanation: Dict[str, str]
    alternatives: list

class DishDetailsResponse(BaseModel):
    dish_name: str
    unified_score: float
    component_scores: Dict[str, float]
    ingredients: List[str]
    confidence_score: float

class HealthScoreRequest(BaseModel):
    dish_name: str

class NutrientData(BaseModel):
    protein_g: float
    fibre_g: float
    vita_ug: float
    vitc_mg: float
    iron_mg: float
    calcium_mg: float
    sfa_mg: float

class HealthScoreResponse(BaseModel):
    dish_name: str
    health_score: float
    nutrient_breakdown: Dict[str, Dict[str, float]]

class CarbonScoreRequest(BaseModel):
    dish_name: str

class CarbonScoreResponse(BaseModel):
    dish_name: str
    carbon_score: float
    ingredients_impact: Dict[str, float]

class InteractionRequest(BaseModel):
    dish_name: str
    medications: List[str]

class InteractionResponse(BaseModel):
    dish_name: str
    interaction_score: float
    interactions: List[Dict[str, str]]

@app.exception_handler(Exception)
async def universal_exception_handler(request: Request, exc: Exception):
    error_msg = f"Unhandled exception: {str(exc)}"
    logger.error(error_msg)
    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"message": "Internal server error", "details": str(exc)}
    )

@app.get("/")
async def root():
    """Redirect to the API documentation"""
    return RedirectResponse(url="/docs")

@app.get("/api-info")
async def api_info():
    """Get basic information about the API"""
    return {
        "name": "Aahar Food Intelligence API",
        "version": "1.0.0",
        "description": "Unified scoring system for Indian food nutritional safety",
        "endpoints": [
            {"path": "/", "method": "GET", "description": "Redirects to API documentation"},
            {"path": "/docs", "method": "GET", "description": "Interactive API documentation"},
            {"path": "/score", "method": "POST", "description": "Calculate unified food score"},
            {"path": "/dish/{dish_name}", "method": "GET", "description": "Get dish details"},
            {"path": "/health-score", "method": "POST", "description": "Calculate health score"},
            {"path": "/carbon-score", "method": "POST", "description": "Calculate carbon score"},
            {"path": "/interactions", "method": "POST", "description": "Check drug-food interactions"},
            {"path": "/health", "method": "GET", "description": "API health check"},
            {"path": "/debug/collections", "method": "GET", "description": "Debug endpoint to check MongoDB collections and sample data"}
        ]
    }

@app.post("/score", response_model=ScoreResponse)
async def calculate_score(request: ScoreRequest):
    """Calculate unified food score with medical and environmental factors"""
    logger.info(f"Score requested for dish: {request.dish_name}")
    try:
        logger.debug(f"Starting score calculation for: {request.dish_name}")
        logger.info(f"User context: {request.user_context}")

        scorer = FoodScorer(user_context=request.user_context)
        logger.debug("Scorer initialized successfully")
        
        # Get base scores with debug logging
        health_score = scorer.calculate_health(request.dish_name)
        logger.debug(f"Health score: {health_score}")
        
        # Compute carbon score as a scalar value by taking the mean of the returned array
        raw_carbon_score = scorer._normalize_carbon(request.dish_name)
        carbon_score = np.mean(raw_carbon_score)
        logger.debug(f"Carbon score: {carbon_score}")
        
        interaction_score = None
        if request.user_context and 'medications' in request.user_context:
            logger.info(f"Calculating interaction score for {request.dish_name}")
            interaction_score = scorer.calculate_interaction(
                request.dish_name
            )
            logger.info(f"Interaction score: {interaction_score}")
        
        # Calculate unified score
        unified = (0.4 * health_score) + (0.35 * (1 - carbon_score)) + (0.25 * (1 - interaction_score))
        logger.info(f"Unified score calculated: {unified}")

        # Confidence calculation
        confidence = scorer._calculate_confidence(request.dish_name)

        return {
            "dish_name": request.dish_name,
            "unified_score": round(unified * 100, 1),
            "score_components": {
                "health": round(health_score * 100, 1),
                "carbon": round(carbon_score * 100, 1),
                "interactions": round(interaction_score * 100, 1) if interaction_score else None
            },
            "confidence_interval": confidence,
            "explanation": {
                "health_breakdown": "ICMR-aligned nutrient balance",
                "carbon_factors": "MP-adjusted CO2e values",
                "interaction_risks": "Drug-food interaction hierarchy"
            },
            "alternatives": get_alternative_suggestions(request.dish_name)
        }
        
    except Exception as e:
        logger.error(f"Critical error processing {request.dish_name}: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/dish/{dish_name}", response_model=DishDetailsResponse)
async def get_dish_details(dish_name: str):
    """Get comprehensive details about a specific dish"""
    try:
        logger.info(f"Looking up dish details for: {dish_name}")
        scorer = FoodScorer()
        details = await scorer.get_dish_details(dish_name)
        return details
    except ValueError as e:
        logger.error(f"Dish not found: {dish_name} - {str(e)}")
        raise HTTPException(status_code=404, detail=f"Dish not found: {dish_name} - {str(e)}")
    except Exception as e:
        logger.error(f"Error retrieving dish details: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

# Helper function to clean ingredient names
def clean_ingredient_name(ingredient: str) -> str:
    """
    Clean ingredient names by removing quantities, units, and preparation instructions.
    For example: '2 potatoes (aloo) - pressure cooked' -> 'potatoes'
    """
    # Remove quantity at the beginning (e.g., "2", "1/2 cup", etc.)
    cleaned = re.sub(r'^[\d\s/]+(cup|tablespoon|teaspoon|whole)?s?\s*', '', ingredient, flags=re.IGNORECASE)
    
    # Remove preparation methods (e.g., "- chopped", "- sliced", etc.)
    cleaned = re.sub(r'\s*-\s*\w+.*$', '', cleaned)
    
    # Remove text in parentheses (e.g., "(aloo)")
    cleaned = re.sub(r'\s*\([^)]*\)', '', cleaned)
    
    # Remove "to taste" and similar instructions
    cleaned = re.sub(r'\s*to taste.*$', '', cleaned)
    
    # Additional cleaning for specific cases
    if 'salt' in cleaned.lower():
        cleaned = 'salt'
    if 'cheese' in cleaned.lower():
        cleaned = 'cheese'
    if 'egg' in cleaned.lower():
        cleaned = 'egg'
    
    return cleaned.strip()

@app.post("/health-score", response_model=HealthScoreResponse)
async def calculate_health_score(request: HealthScoreRequest):
    """Calculate health score for a dish based on nutritional content"""
    try:
        logger.info(f"Health score requested for: {request.dish_name}")
        scorer = FoodScorer()
        
        # Get the health score
        health_score = scorer.calculate_health(request.dish_name)
        logger.info(f"Calculated health score: {health_score}")
        
        # Get nutrient breakdown from the database
        ingredients = scorer._get_ingredients(request.dish_name)
        logger.info(f"Ingredients: {ingredients}")
        
        # Clean ingredient names for better matching
        # Use our local clean_ingredient_name function
        clean_ingredients = [clean_ingredient_name(ing) for ing in ingredients]
        logger.info(f"Cleaned ingredients for nutrient lookup: {clean_ingredients}")
        
        # Try exact match with cleaned ingredients
        nutrients = list(scorer.db.nutrition.find({'food_name': {'$in': clean_ingredients}}))
        logger.info(f"Found {len(nutrients)} direct nutrient matches")
        
        # If no nutrients found, try with regex
        if not nutrients:
            logger.info("No exact nutrient matches, trying regex matching")
            nutrients = []
            for ingredient in clean_ingredients:
                if not ingredient or len(ingredient) < 3:
                    continue  # Skip very short or empty ingredients
                    
                regex_query = {'food_name': {'$regex': f".*{ingredient}.*", '$options': 'i'}}
                matches = list(scorer.db.nutrition.find(regex_query))
                if matches:
                    logger.info(f"Found {len(matches)} regex matches for '{ingredient}'")
                    nutrients.extend(matches)
        
        logger.info(f"Total nutrients found: {len(nutrients)}")
        
        # Prepare nutrient breakdown
        nutrient_breakdown = {}
        for nutrient in nutrients:
            food_name = nutrient.get('food_name', 'unknown')
            logger.info(f"Adding nutrient data for: {food_name}")
            
            # Extract relevant nutrient information with error handling
            try:
                nutrient_data = {
                    'protein_g': float(nutrient.get('protein_g', 0)),
                    'fibre_g': float(nutrient.get('fibre_g', 0)),
                    'vita_ug': float(nutrient.get('vita_ug', 0)),
                    'vitc_mg': float(nutrient.get('vitc_mg', 0)),
                    'iron_mg': float(nutrient.get('iron_mg', 0)),
                    'calcium_mg': float(nutrient.get('calcium_mg', 0)),
                    'sfa_mg': float(nutrient.get('sfa_mg', 0))
                }
                nutrient_breakdown[food_name] = nutrient_data
            except Exception as e:
                logger.error(f"Error processing nutrient data for {food_name}: {str(e)}")
                logger.error(f"Nutrient data: {nutrient}")
        
        logger.info(f"Prepared nutrient breakdown for {len(nutrient_breakdown)} items")
        
        result = {
            "dish_name": request.dish_name,
            "health_score": round(health_score * 100, 1),
            "nutrient_breakdown": nutrient_breakdown
        }
        logger.info(f"Returning response with health score: {result['health_score']}")
        return result
        
    except Exception as e:
        logger.error(f"Error calculating health score: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/carbon-score", response_model=CarbonScoreResponse)
async def calculate_carbon_score(request: CarbonScoreRequest):
    """Calculate carbon footprint score for a dish"""
    try:
        logger.info(f"Carbon score requested for: {request.dish_name}")
        scorer = FoodScorer()
        carbon_scores = scorer._normalize_carbon(request.dish_name)
        ingredients = scorer._get_ingredients(request.dish_name)
        
        logger.info(f"Retrieved {len(ingredients)} ingredients for carbon calculation")
        
        # Clean ingredient names for better matching
        clean_ingredients = [clean_ingredient_name(ing) for ing in ingredients]
        logger.info(f"Cleaned ingredients for carbon lookup: {clean_ingredients}")
        
        # Try exact match with cleaned ingredients
        carbon_data = list(scorer.db.carbon_footprint.find({'food_item': {'$in': clean_ingredients}}))
        logger.info(f"Found {len(carbon_data)} direct carbon footprint matches")
        
        # If very few matches found, try with regex
        if len(carbon_data) < len(clean_ingredients) // 2:
            logger.info("Few carbon footprint matches, trying regex matching")
            for ingredient in clean_ingredients:
                if not ingredient or len(ingredient) < 3:
                    continue  # Skip very short or empty ingredients
                    
                regex_query = {'food_item': {'$regex': f".*{ingredient}.*", '$options': 'i'}}
                matches = list(scorer.db.carbon_footprint.find(regex_query))
                if matches:
                    logger.info(f"Found {len(matches)} regex carbon matches for '{ingredient}'")
                    carbon_data.extend(matches)
        
        # Map ingredients to carbon impact
        ingredients_impact = {}
        for data in carbon_data:
            food_item = data.get('food_item', 'unknown')
            cf_value = data.get('CF_median', 0)
            logger.info(f"Adding carbon impact for {food_item}: {cf_value}")
            ingredients_impact[food_item] = cf_value
        
        # Recalculate carbon score if we found impacts
        final_score = 0.5  # Default value
        if ingredients_impact:
            # Calculate weighted average of carbon impacts
            impact_values = list(ingredients_impact.values())
            if impact_values:
                # Normalize to a 0-1 scale (higher value = higher carbon footprint)
                max_impact = max(100, max(impact_values))  # Cap at reasonable maximum
                final_score = sum(impact_values) / len(impact_values) / max_impact
                logger.info(f"Calculated carbon score from impacts: {final_score}")
        else:
            # Fallback to the scorer's calculation
            final_score = np.mean(carbon_scores)
            logger.info(f"Using default carbon score: {final_score}")
        
        return {
            "dish_name": request.dish_name,
            "carbon_score": round(final_score * 100, 1),
            "ingredients_impact": ingredients_impact
        }
    except Exception as e:
        logger.error(f"Error calculating carbon score: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/interactions", response_model=InteractionResponse)
async def check_interactions(request: InteractionRequest):
    """Check for drug-food interactions"""
    try:
        scorer = FoodScorer(user_context={"medications": request.medications})
        interaction_score = scorer.calculate_interaction(
            request.dish_name
        )
        
        # Get detailed interaction information
        ingredients = scorer._get_ingredients(request.dish_name)
        interactions = scorer.db.interactions.find({
            'drug': {'$in': request.medications},
            'food': {'$in': ingredients}
        })
        
        interaction_details = []
        for interaction in interactions:
            interaction_details.append({
                "drug": interaction['drug'],
                "food": interaction['food'],
                "severity": interaction['severity'],
                "description": interaction.get('description', 'No description available')
            })
        
        return {
            "dish_name": request.dish_name,
            "interaction_score": round(interaction_score * 100, 1),
            "interactions": interaction_details
        }
    except Exception as e:
        logger.error(f"Error checking interactions: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/debug/collections")
async def debug_collections():
    """Debug endpoint to check MongoDB collections and sample data"""
    try:
        scorer = FoodScorer()
        result = {
            "connection": "successful",
            "database": scorer.db.name,
            "collections": {}
        }
        
        # Get all collections
        collections = scorer.db.list_collection_names()
        result["collections_list"] = collections
        
        # Sample data from each collection
        for collection_name in collections:
            collection = scorer.db[collection_name]
            sample = list(collection.find().limit(1))
            # Convert ObjectId to string for JSON serialization
            if sample:
                for doc in sample:
                    if '_id' in doc:
                        doc['_id'] = str(doc['_id'])
                result["collections"][collection_name] = {
                    "count": collection.count_documents({}),
                    "sample": sample
                }
            else:
                result["collections"][collection_name] = {
                    "count": 0,
                    "sample": "No documents found"
                }
        
        return result
    except Exception as e:
        logger.error(f"Error in debug endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            "connection": "failed",
            "error": str(e)
        }

def get_alternative_suggestions(dish_name: str) -> list:
    """Get healthier/safer alternative suggestions"""
    # Implementation would query MongoDB for similar dishes with better scores
    return [{"name": "Suggested Alternative", "score": 85}]

def main():
    # Using hard-coded port 8765
    uvicorn.run(app, host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    main()