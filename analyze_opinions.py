#!/usr/bin/env python3
import json
import os
from collections import Counter
import pandas as pd
import matplotlib.pyplot as plt
from rich.console import Console
from rich.table import Table

def analyze_opinions(file_path):
    """
    Analyze the raw_opinions.json file to extract various statistics
    """
    console = Console()
    
    console.print("\n[bold cyan]Starting analysis of raw opinions data...[/bold cyan]")
    
    # Check if file exists
    if not os.path.exists(file_path):
        console.print(f"[bold red]Error:[/bold red] File {file_path} not found.")
        return
    
    # Load the JSON data
    console.print(f"Loading data from {file_path}...")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError:
        console.print("[bold red]Error:[/bold red] Failed to parse JSON data.")
        return
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        return
    
    # Basic statistics
    total_entries = len(data)
    console.print(f"Total number of opinions/pendants: [bold green]{total_entries}[/bold green]")
    
    # Extract episode information
    episodes = set()
    for entry in data:
        if "episode_id" in entry:
            episodes.add(entry["episode_id"])
    
    console.print(f"Number of unique episodes processed: [bold green]{len(episodes)}[/bold green]")
    
    # Extract categories
    categories = []
    for entry in data:
        if "category" in entry:
            categories.append(entry["category"])
    
    unique_categories = sorted(set(categories))
    console.print(f"Number of unique categories: [bold green]{len(unique_categories)}[/bold green]")
    
    # Create a table of unique categories
    category_table = Table(title="Unique Categories")
    category_table.add_column("Category", style="cyan")
    
    for category in unique_categories:
        category_table.add_row(category)
    
    console.print(category_table)
    
    # Analyze category distribution
    category_counts = Counter(categories)
    
    # Create a table for category distribution
    distribution_table = Table(title="Category Distribution")
    distribution_table.add_column("Category", style="cyan")
    distribution_table.add_column("Count", style="green")
    distribution_table.add_column("Percentage", style="yellow")
    
    for category, count in category_counts.most_common():
        percentage = (count / total_entries) * 100
        distribution_table.add_row(
            category,
            str(count),
            f"{percentage:.2f}%"
        )
    
    console.print(distribution_table)
    
    # Generate a visualization if matplotlib is available
    try:
        # Create a pandas DataFrame for easier visualization
        df = pd.DataFrame(list(category_counts.items()), columns=['Category', 'Count'])
        df = df.sort_values('Count', ascending=False)
        
        # Create a bar chart
        plt.figure(figsize=(12, 8))
        plt.bar(df['Category'], df['Count'], color='skyblue')
        plt.xlabel('Category')
        plt.ylabel('Count')
        plt.title('Distribution of Opinions by Category')
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        
        # Save the chart
        output_path = 'category_distribution.png'
        plt.savefig(output_path)
        console.print(f"[bold green]Visualization saved to:[/bold green] {output_path}")
        
    except ImportError:
        console.print("[yellow]Warning:[/yellow] matplotlib or pandas not available. Skipping visualization.")
    
    # Return data for further analysis if needed
    return {
        "total_entries": total_entries,
        "unique_episodes": len(episodes),
        "unique_categories": unique_categories,
        "category_distribution": dict(category_counts)
    }

if __name__ == "__main__":
    file_path = "data/intermediate/raw_opinions.json"
    analyze_opinions(file_path) 