import os
import pandas as pd
from pymongo import MongoClient
from fuzzywuzzy import process, fuzz
import jellyfish
import logging
import re
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL")

class FoodDataProcessor:
    def __init__(self, mongo_uri=MONGO_URL):
        self.client = MongoClient(mongo_uri)
        self.db = self.client['Aahar']

    def _load_nutrition(self):
        try:
            nutrition = pd.read_csv("Anuvaad_INDB_2024.11.csv", encoding="latin1")
            return nutrition
        except Exception as e:
            raise

    def _load_recipes(self):
        try:
            recipes = pd.read_csv("IndianFoodDatasetXLS.csv", encoding="latin1")
            return recipes
        except Exception as e:
            raise

    def _load_carbon(self):
        try:
            if not os.path.exists("SuEatableLife.csv"):
                raise FileNotFoundError("Carbon footprint CSV file not found")
            
            carbon = pd.read_csv("SuEatableLife.csv")
            
            carbon.rename(columns={
                'FOOD COMMODITY GROUP': 'food_group',
                'Food commodity ITEM': 'food_item',
                'Carbon Footprint kg CO2eq/kg or l of food ITEM': 'CF_median'
            }, inplace=True)
            
            return carbon
            
        except Exception as e:
            raise


    def _fuzzy_match(self, target, choices):
        matches = []
        for choice in choices:
            lev_score = fuzz.ratio(target, choice)
            meta_score = jellyfish.metaphone(target) == jellyfish.metaphone(choice)
            matches.append((choice, lev_score + (100 if meta_score else 0)))
        return max(matches, key=lambda x: x[1])[0]

    def process_nutrition(self):
        nutrition = self._load_nutrition()
        mp_sources = ['Soybean (MP)', 'Chana (MP)', 'Milk (MP)']
        nutrition['mp_adjusted'] = nutrition.apply(
            lambda x: x['energy_kcal'] * 1.12 if x['primarysource'] in mp_sources else x['energy_kcal'],
            axis=1
        )
        nutrition.fillna({
            'protein_g': nutrition.groupby('primarysource')['protein_g'].transform('median'),
            'fibre_g': nutrition['fibre_g'].median(),
            'sfa_mg': nutrition['sfa_mg'].mean()
        }, inplace=True)
        self.db.nutrition.insert_many(nutrition.to_dict('records'))

    def process_recipes(self):
        recipes = self._load_recipes()
        
        # Process each recipe
        for recipe in recipes.to_dict('records'):
            # Clean ingredients
            if 'Ingredients' in recipe:
                ingredients_list = recipe['Ingredients'].split(',')
                # Clean each ingredient - remove quantities and parentheses
                clean_ingredients = []
                for ingredient in ingredients_list:
                    # Extract main ingredient name
                    ingredient = re.sub(r'^[\d\-/\s]+', '', ingredient)  # Remove quantities
                    ingredient = re.sub(r'\(.*?\)', '', ingredient)  # Remove parentheses
                    ingredient = ingredient.strip().lower()
                    if ingredient:
                        clean_ingredients.append(ingredient)
                recipe['ingredients_clean'] = clean_ingredients
            
            self.db.recipes.insert_one(recipe)

    def process_carbon_data(self):
        carbon = self._load_carbon()
        required_columns = ['food_item', 'CF_median', 'food_group']
        if not all(col in carbon.columns for col in required_columns):
            raise ValueError(f"Missing required columns in carbon footprint data: {required_columns}")
        
        carbon['CF_median'] = pd.to_numeric(carbon['CF_median'], errors='coerce')
        carbon = carbon.dropna(subset=['CF_median'])
        
        mp_adjustments = {
            'meat': 1.18,
            'dairy': 1.07,
            'cereals': 0.92
        }
        carbon['mp_adjusted'] = carbon.apply(
            lambda x: x['CF_median'] * mp_adjustments.get(x['food_group'].lower(), 1.0),
            axis=1
        )
        
        self.db.carbon_footprint.insert_many(carbon.to_dict('records'))

    def process_interactions(self):
        if not os.path.exists("drug_food_interactions.csv"):
            logging.warning("drug_food_interactions.csv file not found. Skipping interactions processing.")
            return
        try:
            interactions = pd.read_csv("drug_food_interactions.csv", encoding="latin1")
            severity_map = {'Critical': 1.0, 'Severe': 0.7, 'Moderate': 0.4}
            interactions['severity'] = interactions['risk_level'].map(severity_map)
            self.db.interactions.insert_many(interactions.to_dict('records'))
        except Exception as e:
            raise