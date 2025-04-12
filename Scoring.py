# scoring.py
from scipy.stats import beta
import numpy as np
from pymongo import MongoClient
from typing import List, Optional, Dict
import re 
import os
from dotenv import load_dotenv

load_dotenv()
MONGO_URL = os.getenv("MONGO_URL")

class FoodScorer:
    def __init__(self, user_context: Optional[Dict] = None):
        # Initialize MongoDB connection with proper error handling
        try:
            self.client = MongoClient(MONGO_URL)
            self.db = self.client['Aahar']
        except Exception as e:
            raise ConnectionError(f"Failed to connect to MongoDB: {str(e)}")
        self.user_context = user_context or {}
        
    def _identify_input_type(self, name: str) -> str:
        """Improved input detection with case insensitivity"""
        # First check recipes with case-insensitive partial match
        recipe = self.db.recipes.find_one({
            "TranslatedRecipeName": {"$regex": name.strip(), "$options": "i"}
        })
        if recipe:
            return "dish"
        
        # Check nutrition data with fuzzy matching
        nutrition_match = self.db.nutrition.find_one({
            "food_name": {"$regex": f"^{name.strip()}$", "$options": "i"}
        })
        if nutrition_match:
            return "ingredient"
        
        # Check carbon footprint data
        carbon_match = self.db.carbon_footprint.find_one({
            "food_item": {"$regex": f"^{name.strip()}$", "$options": "i"}
        })
        if carbon_match:
            return "ingredient"
            
        # Final check using recipe ingredients
        if self.db.recipes.find_one({
            "ingredients_clean": {"$regex": name.strip(), "$options": "i"}
        }):
            return "dish"
            
        raise ValueError(f"Unrecognized food item: {name}. Please check spelling or submit new food data.")

    def _get_ingredients(self, name: str) -> List[str]:
        """
        Retrieve the ingredients from a dish. If the dish exists, gives priority to the
        'ingredients_clean' field but falls back to the original 'Ingredients' if necessary.
        """
        try:
            input_type = self._identify_input_type(name)
        except ValueError:
            # Treat novel or unknown items as an ingredient by itself.
            return [name]

        # If the input is identified as a dish try fetching the recipe.
        if input_type == "dish":
            recipe = self.db.recipes.find_one({
                "TranslatedRecipeName": {"$regex": f"^{name}$", "$options": "i"}
            })
            if recipe:
                # Check if a cleaned ingredients list exists.
                ingredients = recipe.get("ingredients_clean")
                if ingredients:
                    # Ensure that we've got a list. Sometimes it might be stored as a comma‐separated string.
                    if not isinstance(ingredients, list):
                        if isinstance(ingredients, str):
                            ingredients = [
                                i.strip().lower() 
                                for i in ingredients.split(',') if i.strip()
                            ]
                        else:
                            ingredients = [ingredients]
                    return ingredients
                # Fall back to using the original Ingredients field if available.
                elif "Ingredients" in recipe and recipe["Ingredients"]:
                    ingredients_field = recipe["Ingredients"]
                    if isinstance(ingredients_field, str):
                        return [i.strip().lower() for i in ingredients_field.split(',') if i.strip()]
                    elif isinstance(ingredients_field, list):
                        return ingredients_field
            return [name]
        # Otherwise, treat as a single ingredient.
        return [name]

    def _normalize_carbon(self, name: str):
        ingredients = self._get_ingredients(name)
        if not ingredients:
            return np.array([0.5])
        query = {'food_item': {'$in': ingredients}}
        carbon_data = list(self.db.carbon_footprint.find(query))
        # If no carbon data is available, return a default value.
        if not carbon_data:
            return np.array([0.5])
        # Assuming each entry contains a 'CF_median' field.
        cf_values = []
        for data in carbon_data:
            try:
                cf_values.append(float(data.get("CF_median", 0)))
            except ValueError:
                continue
        if not cf_values:
            return np.array([0.5])
        a, b = 2, 5  # Shape parameters for beta distribution scaling.
        normalized = [beta.cdf(val, a, b) for val in cf_values]
        return np.array(normalized)
    
    def _clean_ingredient_name(self, ingredient: str) -> str:
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
    
    def calculate_health(self, name: str):
        ingredients = self._get_ingredients(name)
        print(f"Ingredients for {name}: {ingredients}")
        if not ingredients:
            return 0.5  # Default average health score for unknown items
            
        # Clean ingredient names for better matching
        clean_ingredients = [self._clean_ingredient_name(ing) for ing in ingredients]
        print(f"Cleaned ingredients: {clean_ingredients}")
            
        # First, try to find nutrition data for the dish name itself
        dish_nutrients = list(self.db.nutrition.find({'food_name': name}))
        if dish_nutrients:
            print(f"Found direct nutrition data for dish: {name}")
            nutrients = dish_nutrients
        else:
            # If no direct match, search for individual ingredients using cleaned names
            query = {'food_name': {'$in': clean_ingredients}}
            nutrients = list(self.db.nutrition.find(query))
            print(f"Found {len(nutrients)} nutrient records for ingredients")
            
            # If no nutrients found for exact ingredients, try a more flexible approach with regex
            if not nutrients:
                print("Trying more flexible ingredient matching...")
                nutrients = []
                for ingredient in clean_ingredients:
                    if not ingredient or len(ingredient) < 3:
                        continue  # Skip very short or empty ingredients
                        
                    # Try to find similar ingredient names using regex
                    regex_query = {'food_name': {'$regex': f".*{ingredient}.*", '$options': 'i'}}
                    matches = list(self.db.nutrition.find(regex_query))
                    if matches:
                        print(f"Found {len(matches)} matches for {ingredient}")
                        nutrients.extend(matches)
        
        # ICMR-based scoring weights for positive nutrients
        positive_weights = {
            'protein_g': 0.25,
            'fibre_g': 0.15,
            'vita_ug': 0.1,
            'vitc_mg': 0.1,
            'iron_mg': 0.15,
            'calcium_mg': 0.15,
        }
        
        # Separate handling for saturated fats
        negative_key = 'sfa_mg'
        
        scores = []
        for nutrient in nutrients:
            print(f"Processing nutrient for: {nutrient.get('food_name', 'unknown')}")
            
            # Calculate positive nutrient score
            positive_score = 0
            for key, weight in positive_weights.items():
                # Try to find the actual key in the document that matches or contains the key
                matching_keys = [k for k in nutrient.keys() if key.lower() in k.lower()]
                
                if matching_keys:
                    actual_key = matching_keys[0]
                    try:
                        value = float(nutrient.get(actual_key, 0))
                        positive_score += weight * value
                        print(f"  {actual_key}: {value} * {weight} = {weight * value}")
                    except (ValueError, TypeError):
                        print(f"  Could not convert {actual_key} value to float: {nutrient.get(actual_key)}")
                else:
                    print(f"  No matching key found for {key}")
            
            # Get saturated fat value and handle it separately
            negative_score = 0
            negative_keys = [k for k in nutrient.keys() if negative_key.lower() in k.lower()]
            if negative_keys:
                actual_key = negative_keys[0]
                try:
                    sfa_value = float(nutrient.get(actual_key, 0))
                    # Cap SFA penalty to prevent overly negative scores
                    # Using a sigmoid-like function to map high SFA to a capped penalty
                    # This limits the negative impact while still penalizing high SFA
                    sfa_penalty = min(0.2, 0.1 * (sfa_value / 1000))
                    negative_score = sfa_penalty
                    print(f"  {actual_key}: {sfa_value} → penalty: {sfa_penalty}")
                except (ValueError, TypeError):
                    print(f"  Could not convert {actual_key} value to float: {nutrient.get(actual_key)}")
            
            # Calculate combined nutrient score
            nutrient_score = positive_score - negative_score
            
            # Ensure we don't have unrealistic values
            if nutrient_score > 0:
                # Normalize to 0-1 range with a more realistic denominator
                normalized_score = max(min(nutrient_score / 50, 1), 0)
                scores.append(normalized_score)
                print(f"  Final normalized score: {normalized_score}")
            else:
                # Even for negative scores, assign a small positive value to avoid completely ignoring nutrient data
                min_score = 0.05
                scores.append(min_score)
                print(f"  Low score adjusted to minimum: {min_score}")
        
        # Return default value if no valid scores were calculated
        if not scores:
            print("No valid scores calculated, returning default value of 0.5")
            return 0.5
            
        final_score = np.mean(scores)
        print(f"Final health score: {final_score}")
        return final_score

    def calculate_interaction(self, name: str):
        ingredients = self._get_ingredients(name)
        if not ingredients:
            return 0
            
        medications = self.user_context.get('medications', [])
        # Ensure medications is a list.
        if not isinstance(medications, list):
            medications = [medications]
        query = {
            'drug': {'$in': medications},
            'food': {'$in': ingredients}
        }
        
        interactions = list(self.db.interactions.find(query))
        return max(i['severity'] for i in interactions) if interactions else 0

    def unified_score(self, dish_name):
        # Get recipe decomposition with case-insensitive search
        recipe = self.db.recipes.find_one({
            'TranslatedRecipeName': {"$regex": dish_name.strip(), "$options": "i"}
        })
        
        if not recipe:
            raise ValueError(f"Recipe not found: {dish_name}")
        
        # Fetch ingredients ensuring a list is returned.
        ingredients = recipe.get('ingredients_clean', [])
        if not ingredients or not isinstance(ingredients, list):
            if 'Ingredients' in recipe and recipe['Ingredients']:
                ingredients = [
                    i.strip().lower() 
                    for i in recipe['Ingredients'].split(',') if i.strip()
                ]
            else:
                ingredients = []
        
        # Calculate components
        H = self.calculate_health(dish_name)
        C = self._normalize_carbon(dish_name)
        
        # Final score (redistributed weights: 53% health, 47% carbon footprint)
        unified = 0.53*H + 0.47*(1-np.mean(C))
        return round(unified * 100, 1)

    async def get_dish_details(self, dish_name: str) -> Dict:
        """Get comprehensive dish details including scores and explanations"""
        try:
            score = self.unified_score(dish_name)
            recipe = self.db.recipes.find_one({'TranslatedRecipeName': dish_name})
            
            if not recipe:
                raise ValueError(f"Recipe not found: {dish_name}")
            
            # Ensure ingredients are a list.
            ingredients = recipe.get('ingredients_clean', [])
            if not ingredients or not isinstance(ingredients, list):
                if 'Ingredients' in recipe and recipe['Ingredients']:
                    ingredients = [
                        i.strip().lower() 
                        for i in recipe['Ingredients'].split(',') if i.strip()
                    ]
                else:
                    ingredients = []
            
            health_score = self.calculate_health(dish_name)
            carbon_scores = self._normalize_carbon(dish_name)
            
            return {
                'dish_name': dish_name,
                'unified_score': score,
                'component_scores': {
                    'health_score': round(health_score * 100, 1),
                    'carbon_score': round((1 - np.mean(carbon_scores)) * 100, 1),
                },
                'ingredients': ingredients,
                'confidence_score': self._calculate_confidence(dish_name)
            }
        except Exception as e:
            raise ValueError(f"Error calculating scores: {str(e)}")

    def _calculate_confidence(self, dish_name: str) -> float:
        """Calculate confidence score based on data completeness"""
        # First get the recipe and its ingredients
        recipe = self.db.recipes.find_one({
            "TranslatedRecipeName": {"$regex": dish_name.strip(), "$options": "i"}
        })
        
        if not recipe:
            return 0.0
        
        # Extract the ingredients ensuring we work with a list.
        ingredients = recipe.get('ingredients_clean', [])
        if not ingredients or not isinstance(ingredients, list):
            if 'Ingredients' in recipe and recipe['Ingredients']:
                ingredients = [
                    i.strip().lower() 
                    for i in recipe['Ingredients'].split(',') if i.strip()
                ]
            else:
                ingredients = []
        
        if not ingredients:
            return 0.0
        
        total = len(ingredients)
        # Make sure ingredients is a list before using $in
        found_nutrition = len(list(self.db.nutrition.find({
            'food_name': {'$in': ingredients}
        })))
        found_carbon = len(list(self.db.carbon_footprint.find({
            'food_item': {'$in': ingredients}
        })))
        
        return round((found_nutrition + found_carbon) / (total * 2) * 100, 1)