# mongodb_loader.py
import logging
from data_pipeline import FoodDataProcessor

def main():
    processor = FoodDataProcessor()

    # Process nutrition data separately
    try:
        logging.info('Processing nutrition data...')
        processor.process_nutrition()
    except Exception as e:
        logging.error("Failed processing nutrition data: %s", e)

    # Process carbon footprint data separately
    try:
        logging.info('Processing carbon data...')
        processor.process_carbon_data()
    except Exception as e:
        logging.error("Failed processing carbon data: %s", e)

    # Process recipes data separately
    try:
        logging.info('Processing recipes data...')
        processor.process_recipes()
    except Exception as e:
        logging.error("Failed processing recipes data: %s", e)

    # Process interactions data separately
    try:
        logging.info('Processing interactions data...')
        processor.process_interactions()
    except Exception as e:
        logging.error("Failed processing interactions data: %s", e)

    # Create indexes after all datasets are processed
    try:
        logging.info('Creating indexes...')
        processor.db.nutrition.create_index([('food_name', 'text')])
        processor.db.carbon_footprint.create_index([('food_item', 'text')])
        processor.db.recipes.create_index([('ingredients_clean', 1)])
        processor.db.interactions.create_index([('drug', 1), ('food', 1)])
    except Exception as e:
        logging.error("Failed creating indexes: %s", e)

    processor.client.close()

if __name__ == '__main__':
    main()