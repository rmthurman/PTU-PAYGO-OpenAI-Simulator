"""
Pricing and model configuration module.

Handles loading of OpenAI pricing data and model configurations
from JSON files.
"""

import json
from typing import Dict, List, Tuple, Any


def load_local_json(path: str) -> Dict[str, Any]:
    """Load and parse a local JSON file.
    
    Args:
        path: Path to the JSON file
        
    Returns:
        Parsed JSON data as dictionary
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading {path}: {e}")
        return {}


def _extract_model_groups(obj: Dict[str, Any]) -> List[str]:
    """Extract model group names from pricing data structure."""
    def walk(o):
        if isinstance(o, dict):
            if 'models' in o:
                return list(o['models'].keys())
            else:
                results = []
                for v in o.values():
                    if isinstance(v, (dict, list)):
                        results.extend(walk(v))
                return results
        elif isinstance(o, list):
            results = []
            for item in o:
                results.extend(walk(item))
            return results
        return []
    
    return walk(obj)


def _extract_input_output_prices(path: str, model_list: List[str]) -> Dict[str, Tuple[float, float]]:
    """Extract input and output prices for models from pricing JSON.
    
    Args:
        path: Path to pricing JSON file
        model_list: List of model names to extract prices for
        
    Returns:
        Dictionary mapping model names to (input_price, output_price) tuples
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            pricing_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    
    model_prices = {}
    
    def search_for_prices(obj, model_name):
        """Recursively search for pricing data for a specific model."""
        if isinstance(obj, dict):
            # Check if this is a model pricing entry
            if 'input' in obj and 'output' in obj:
                try:
                    input_price = float(obj['input'])
                    output_price = float(obj['output'])
                    return (input_price, output_price)
                except (ValueError, TypeError):
                    pass
            
            # Check if this dict contains the model
            if 'models' in obj and model_name in obj['models']:
                model_data = obj['models'][model_name]
                if isinstance(model_data, dict) and 'input' in model_data and 'output' in model_data:
                    try:
                        input_price = float(model_data['input'])
                        output_price = float(model_data['output'])
                        return (input_price, output_price)
                    except (ValueError, TypeError):
                        pass
            
            # Recursively search in nested structures
            for key, value in obj.items():
                if model_name.lower() in key.lower() or key.lower() in model_name.lower():
                    result = search_for_prices(value, model_name)
                    if result:
                        return result
                        
                # Also search in all nested objects
                result = search_for_prices(value, model_name)
                if result:
                    return result
                    
        elif isinstance(obj, list):
            for item in obj:
                result = search_for_prices(item, model_name)
                if result:
                    return result
        
        return None
    
    for model in model_list:
        prices = search_for_prices(pricing_data, model)
        if prices:
            model_prices[model] = prices
    
    return model_prices


def load_pricing_data(pricing_file: str = "info.json") -> Tuple[List[str], Dict[str, Tuple[float, float]]]:
    """Load OpenAI pricing data and extract model information.
    
    Args:
        pricing_file: Path to the pricing JSON file (default: info.json)
        
    Returns:
        Tuple of (model_list, model_prices_dict)
    """
    # Try to load from existing files, fallback to defaults
    pricing_data = load_local_json(pricing_file)
    
    # Default model list and prices (using original app defaults)
    default_models = [
        "gpt-4.1", "gpt-4-turbo", "gpt-4o", "gpt-4o-mini", 
        "gpt-3.5-turbo", "text-embedding-ada-002"
    ]
    
    # Use the original app's default pricing: input $0.002, output $0.008
    default_prices = {
        "gpt-4.1": (0.0020, 0.0080),
        "gpt-4-turbo": (0.0020, 0.0080), 
        "gpt-4o": (0.0020, 0.0080),
        "gpt-4o-mini": (0.0020, 0.0080),
        "gpt-3.5-turbo": (0.0020, 0.0080),
        "text-embedding-ada-002": (0.0020, 0.0080)
    }
    
    if pricing_data:
        # Try to extract models and prices from the loaded data
        model_list = _extract_model_groups(pricing_data)
        if model_list:
            model_prices = _extract_input_output_prices(pricing_file, model_list)
            if model_prices:
                return model_list, model_prices
    
    # Fallback to defaults
    return default_models, default_prices


def get_price_ratio(input_price: float, output_price: float) -> float:
    """Calculate the ratio of output price to input price.
    
    Args:
        input_price: Price per 1K input tokens
        output_price: Price per 1K output tokens
        
    Returns:
        Ratio of output_price / input_price
    """
    if input_price == 0:
        return 1.0  # Fallback ratio
    return output_price / input_price