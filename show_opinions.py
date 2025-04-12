#!/usr/bin/env python3
"""
Show opinions from the repository and their relationships.

This script loads all opinions from the repository and displays them
with their key information and relationships.
"""

from src.repositories.opinion_repository import OpinionRepository
from src.repositories.category_repository import CategoryRepository

def main():
    """Load and display all opinions and their relationships."""
    # Initialize repositories
    opinion_repo = OpinionRepository("data/json/opinions.json")
    category_repo = CategoryRepository("data/json/categories.json")
    
    # Get all opinions
    all_opinions = opinion_repo.get_all_opinions()
    print(f"Found {len(all_opinions)} total opinions\n")
    
    # Create a lookup dictionary for quick access
    opinion_lookup = {opinion.id: opinion for opinion in all_opinions}
    
    # Get all categories
    all_categories = category_repo.get_all_categories()
    category_lookup = {category.id: category.name for category in all_categories}
    
    # Display opinions
    for opinion in all_opinions:
        # Get category name
        category_name = category_lookup.get(opinion.category_id, opinion.category_id)
        
        # Count appearances
        num_appearances = len(opinion.appearances)
        
        # Display basic info
        print(f"Opinion: {opinion.id} - {opinion.title}")
        print(f"Category: {category_name}")
        print(f"Description: {opinion.description[:100]}...")
        print(f"Appearances: {num_appearances}")
        
        # Display all episodes where this opinion appears
        episodes = [app.episode_title for app in opinion.appearances]
        if episodes:
            print(f"Episodes: {', '.join(episodes)}")
        
        # Display relationships
        if opinion.related_opinions:
            print("Related opinions:")
            for related_id in opinion.related_opinions:
                related_opinion = opinion_lookup.get(related_id)
                if related_opinion:
                    print(f"  → {related_id}: {related_opinion.title}")
                else:
                    print(f"  → {related_id}: (Not found)")
        
        # Display contradictions if any
        if opinion.is_contradiction:
            contradicts = opinion_lookup.get(opinion.contradicts_opinion_id)
            if contradicts:
                print(f"Contradicts: {contradicts.id} - {contradicts.title}")
            else:
                print(f"Contradicts: {opinion.contradicts_opinion_id} (Not found)")
        
        # Display evolution chain if any
        if opinion.evolution_chain:
            print("Evolution chain:")
            for chain_id in opinion.evolution_chain:
                chain_op = opinion_lookup.get(chain_id)
                if chain_op:
                    print(f"  → {chain_id}: {chain_op.title}")
                else:
                    print(f"  → {chain_id}: (Not found)")
        
        print("-" * 80)
    
    # Show statistics
    print("\nOpinion Statistics:")
    opinions_by_category = {}
    for opinion in all_opinions:
        category = category_lookup.get(opinion.category_id, opinion.category_id)
        if category in opinions_by_category:
            opinions_by_category[category] += 1
        else:
            opinions_by_category[category] = 1
    
    for category, count in sorted(opinions_by_category.items(), key=lambda x: x[1], reverse=True):
        print(f"{category}: {count} opinions")
    
    # Count relationships
    opinions_with_relations = sum(1 for op in all_opinions if op.related_opinions)
    print(f"\nOpinions with relationships: {opinions_with_relations}")
    
    # Count contradictions
    contradictions = sum(1 for op in all_opinions if op.is_contradiction)
    print(f"Opinions with contradictions: {contradictions}")
    
    # Count evolutions
    evolutions = sum(1 for op in all_opinions if op.evolution_chain)
    print(f"Opinions with evolution chains: {evolutions}")

if __name__ == "__main__":
    main() 