from Scoring import FoodScorer
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def debug_health_score():
    # Initialize the scorer
    print("Initializing FoodScorer...")
    scorer = FoodScorer()
    
    dish_name = "Veg Chili Cheese Burgers Recipe"
    print(f"\nTesting health score for: {dish_name}")
    
    # Get ingredients
    ingredients = scorer._get_ingredients(dish_name)
    print(f"Ingredients for {dish_name}: {ingredients}")
    
    # Check if ingredients are found
    if not ingredients:
        print("ERROR: No ingredients found for this dish")
        return
    
    # Query for nutrition data
    query = {'food_name': {'$in': ingredients}}
    print(f"Query: {query}")
    
    # Check DB connection
    print(f"Database collections: {scorer.db.list_collection_names()}")
    
    # Get nutrition data
    nutrients = list(scorer.db.nutrition.find(query))
    print(f"Found {len(nutrients)} nutrient records for ingredients")
    
    # If no nutrients found, check with alternative query
    if not nutrients:
        print("No nutrients found with food_name query, checking with exact ingredient names...")
        for ingredient in ingredients:
            print(f"Looking for: {ingredient}")
            exact_match = scorer.db.nutrition.find_one({'food_name': ingredient})
            if exact_match:
                print(f"Found exact match for {ingredient}")
            else:
                print(f"No exact match for {ingredient}")
    
    # Attempt to calculate health score
    health_score = scorer.calculate_health(dish_name)
    print(f"Health score: {health_score}")
    
    # Calculate unified score
    try:
        unified_score = scorer.unified_score(dish_name)
        print(f"Unified score: {unified_score}")
    except Exception as e:
        print(f"Error calculating unified score: {str(e)}")

if __name__ == "__main__":
    debug_health_score() 