#!/usr/bin/env python3
"""
Garmin Activity Summary Generator
Generates a PNG image summary similar to Garmin Connect year-end report.
"""

import re
import os

import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime


def parse_time_to_seconds(time_str):
    """Parse time string (HH:MM:SS or HH:MM:SS.s) to total seconds."""
    if not time_str or time_str == "--":
        return 0
    try:
        # Remove quotes if present
        time_str = str(time_str).strip('"')
        # Handle different formats
        parts = time_str.replace(".", ":").split(":")
        if len(parts) >= 3:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = float(parts[2]) if len(parts) > 2 else 0
            return hours * 3600 + minutes * 60 + seconds
        elif len(parts) == 2:
            minutes = int(parts[0])
            seconds = float(parts[1])
            return minutes * 60 + seconds
    except (ValueError, IndexError):
        return 0
    return 0


def parse_number(value):
    """Parse number from string, handling various number formats."""
    if not value or value == "--":
        return 0
    try:
        # Remove quotes
        value = str(value).strip('"')
        # Remove spaces (thousands separator)
        value = value.replace(" ", "").replace("\u00a0", "")

        # Handle mixed format with both separators (e.g., "1.200,5" or "1,200.5")
        if '.' in value and ',' in value:
            # Determine which is thousands and which is decimal by position
            dot_pos = value.rfind('.')
            comma_pos = value.rfind(',')
            if dot_pos > comma_pos:
                # Dot is decimal (e.g., "1,200.5" -> 1200.5)
                value = value.replace(",", "")
            else:
                # Comma is decimal (e.g., "1.200,5" -> 1200.5)
                value = value.replace(".", "").replace(",", ".")
        # Check if dot is thousands separator (e.g., "5.972" or "1.234.567")
        # Pattern: 1-3 digits followed by groups of dot + 3 digits (Czech format)
        elif re.match(r'^\d{1,3}(\.\d{3})+$', value):
            value = value.replace(".", "")
        # Check if comma is thousands separator (e.g., "2,738" or "1,234,567")
        # Pattern: 1-3 digits followed by groups of comma + 3 digits
        elif re.match(r'^\d{1,3}(,\d{3})+$', value):
            value = value.replace(",", "")
        else:
            # Otherwise treat comma as decimal separator
            value = value.replace(",", ".")

        return float(value)
    except ValueError:
        return 0


def format_number(num, decimals=0):
    """Format number with space as thousands separator (Czech style)."""
    if decimals > 0:
        formatted = f"{num:,.{decimals}f}"
    else:
        formatted = f"{int(num):,}"
    # Replace comma with space for Czech formatting
    return formatted.replace(",", " ")


def format_time(total_seconds):
    """Format seconds to 'XXXh YYm' format."""
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    return f"{hours}h {minutes}m"


def load_and_analyze_data(csv_path, year_filter=None):
    """Load CSV and calculate summary statistics."""
    df = pd.read_csv(csv_path, encoding='utf-8')

    # Filter by year if specified
    if year_filter:
        df['Datum'] = pd.to_datetime(df['Datum'])
        df = df[df['Datum'].dt.year == int(year_filter)]
        df['Datum'] = df['Datum'].astype(str)  # Convert back for compatibility

    # Calculate statistics
    stats = {}

    # Total activities count
    stats['total_activities'] = len(df)

    # Most frequent activity
    activity_counts = df['Typ aktivity'].value_counts()
    stats['most_frequent_activity'] = activity_counts.index[0]
    stats['most_frequent_count'] = activity_counts.iloc[0]

    # All activity types with counts
    stats['activity_breakdown'] = activity_counts.to_dict()

    # Total time (parse and sum)
    total_seconds = df['Čas'].apply(parse_time_to_seconds).sum()
    stats['total_time'] = format_time(total_seconds)
    stats['total_time_seconds'] = total_seconds

    # Total distance - swimming is in meters, other activities in km
    def calc_distance(row):
        dist = parse_number(row['Vzdálenost'])
        activity_type = row['Typ aktivity'].lower()
        # Swimming activities are recorded in meters
        if 'plav' in activity_type or 'swim' in activity_type:
            return dist / 1000  # Convert meters to km
        return dist

    total_distance = df.apply(calc_distance, axis=1).sum()
    stats['total_distance'] = total_distance

    # Total elevation gain
    total_elevation = df['Celkový výstup'].apply(parse_number).sum()
    stats['total_elevation'] = total_elevation

    # Total calories
    total_calories = df['Kalorie (kcal)'].apply(parse_number).sum()
    stats['total_calories'] = total_calories

    # Total steps
    total_steps = df['Kroky'].apply(parse_number).sum()
    stats['total_steps'] = total_steps

    # Year from filter or current year
    if year_filter:
        stats['year'] = int(year_filter)
    else:
        stats['year'] = datetime.now().year

    return stats


def create_gradient_background(width, height):
    """Create a blue gradient background similar to Garmin."""
    img = Image.new('RGB', (width, height))
    draw = ImageDraw.Draw(img)

    # Dark blue to lighter blue gradient
    start_color = (0, 40, 80)
    end_color = (0, 80, 140)

    for y in range(height):
        ratio = y / height
        r = int(start_color[0] + (end_color[0] - start_color[0]) * ratio)
        g = int(start_color[1] + (end_color[1] - start_color[1]) * ratio)
        b = int(start_color[2] + (end_color[2] - start_color[2]) * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    return img


def draw_icon(draw, x, y, icon_type, color, size=40):
    """Draw simple icons for each metric."""
    if icon_type == 'steps':
        # Footsteps icon (simplified)
        draw.ellipse([x, y, x+size//2, y+size], fill=color)
        draw.ellipse([x+size//2, y+size//4, x+size, y+size*3//4], fill=color)
    elif icon_type == 'activities':
        # Person with arms up
        draw.ellipse([x+size//3, y, x+size*2//3, y+size//3], fill=color)
        draw.line([x+size//2, y+size//3, x+size//2, y+size*2//3], fill=color, width=3)
        draw.line([x+size//4, y+size//2, x+size*3//4, y+size//2], fill=color, width=3)
        draw.line([x+size//2, y+size*2//3, x+size//4, y+size], fill=color, width=3)
        draw.line([x+size//2, y+size*2//3, x+size*3//4, y+size], fill=color, width=3)
    elif icon_type == 'time':
        # Clock
        draw.ellipse([x, y, x+size, y+size], outline=color, width=3)
        draw.line([x+size//2, y+size//4, x+size//2, y+size//2], fill=color, width=2)
        draw.line([x+size//2, y+size//2, x+size*3//4, y+size//2], fill=color, width=2)
    elif icon_type == 'distance':
        # Road/path
        draw.polygon([(x, y+size), (x+size//3, y), (x+size*2//3, y), (x+size, y+size)], outline=color, width=2)
    elif icon_type == 'elevation':
        # Mountain
        draw.polygon([(x, y+size), (x+size//2, y), (x+size, y+size)], fill=color)
    elif icon_type == 'calories':
        # Flame
        draw.ellipse([x+size//4, y+size//3, x+size*3//4, y+size], fill=color)
        draw.polygon([(x+size//2, y), (x+size//4, y+size//2), (x+size*3//4, y+size//2)], fill=color)
    elif icon_type == 'frequent':
        # Star/badge
        draw.ellipse([x, y, x+size, y+size], outline=color, width=2)
        draw.ellipse([x+size//4, y+size//4, x+size*3//4, y+size*3//4], fill=color)


# Colors for icons
COLORS = {
    'steps': (100, 149, 237),      # Cornflower blue
    'activities': (255, 99, 71),    # Tomato red
    'frequent': (255, 165, 0),      # Orange
    'time': (218, 112, 214),        # Orchid/pink
    'distance': (255, 200, 100),    # Gold
    'elevation': (50, 205, 50),     # Lime green
    'calories': (255, 69, 0),       # Red-orange
}


def generate_summary_image(stats, output_path):
    """Generate the summary image."""
    width = 900
    height = 1000

    # Create gradient background
    img = create_gradient_background(width, height)
    draw = ImageDraw.Draw(img)

    # Try to load fonts, fall back to default
    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
        big_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 42)
        medium_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
    except OSError:
        try:
            title_font = ImageFont.truetype("DejaVuSans-Bold.ttf", 48)
            big_font = ImageFont.truetype("DejaVuSans-Bold.ttf", 42)
            medium_font = ImageFont.truetype("DejaVuSans.ttf", 24)
        except OSError:
            title_font = ImageFont.load_default()
            big_font = title_font
            medium_font = title_font

    # Metrics to display
    y_offset = 60
    x_icon = 50
    x_value = 100
    row_height = 110

    metrics = [
        ('steps', format_number(stats['total_steps']), 'Kroky', COLORS['steps']),
        ('activities', str(stats['total_activities']), 'Celkový počet aktivit', COLORS['activities']),
        ('frequent', f"{stats['most_frequent_count']}x {stats['most_frequent_activity']}", 'Nejčastější aktivita', COLORS['frequent']),
        ('time', stats['total_time'], 'Čas aktivity', COLORS['time']),
        ('distance', f"{format_number(stats['total_distance'], 1)} km", 'Vzdálenost v aktivitě', COLORS['distance']),
        ('elevation', f"{format_number(stats['total_elevation'])} m", 'Výstup aktivity', COLORS['elevation']),
        ('calories', format_number(stats['total_calories']), 'Kalorie v aktivitě', COLORS['calories']),
    ]

    for icon_type, value, label, color in metrics:
        # Draw colored dot/icon indicator
        draw.ellipse([x_icon, y_offset + 15, x_icon + 30, y_offset + 45], fill=color)

        # Draw value
        draw.text((x_value, y_offset), value, font=big_font, fill=(255, 255, 255))

        # Draw label
        draw.text((x_value, y_offset + 55), label, font=medium_font, fill=(150, 180, 210))

        y_offset += row_height

    # Garmin logo text (right side, centered vertically)
    garmin_x = width - 80
    garmin_y = 100
    for letter in "GARMIN":
        bbox = draw.textbbox((0, 0), letter, font=title_font)
        letter_width = bbox[2] - bbox[0]
        draw.text((garmin_x - letter_width // 2, garmin_y), letter, font=title_font, fill=(255, 255, 255))
        garmin_y += 50

    # Connect year text (bottom right, with padding)
    connect_text = f"connect {stats['year']}"
    bbox = draw.textbbox((0, 0), connect_text, font=title_font)
    text_width = bbox[2] - bbox[0]
    draw.text((width - text_width - 50, height - 80), connect_text, font=title_font, fill=(255, 255, 255))

    # Add a subtle line
    draw.line([(50, height - 150), (width - 50, height - 150)], fill=(100, 130, 160), width=1)

    # Save image
    img.save(output_path, 'PNG')
    print(f"Summary image saved to: {output_path}")

    return img


def main():
    # Default paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.environ.get('CSV_PATH', os.path.join(script_dir, 'data', 'Activities.csv'))
    year_filter = os.environ.get('YEAR', None)

    print(f"Reading data from: {csv_path}")
    if year_filter:
        print(f"Filtering for year: {year_filter}")

    # Load and analyze data
    stats = load_and_analyze_data(csv_path, year_filter)

    # Generate output path with year
    output_path = os.path.join(script_dir, 'data', f"garmin-{stats['year']}.png")

    print("\n=== Activity Summary ===")
    print(f"Total activities: {stats['total_activities']}")
    print(f"Most frequent: {stats['most_frequent_activity']} ({stats['most_frequent_count']}x)")
    print(f"Total time: {stats['total_time']}")
    print(f"Total distance: {format_number(stats['total_distance'], 1)} km")
    print(f"Total elevation: {format_number(stats['total_elevation'])} m")
    print(f"Total calories: {format_number(stats['total_calories'])}")
    print(f"Total steps: {format_number(stats['total_steps'])}")
    print("========================\n")

    # Generate image
    generate_summary_image(stats, output_path)


if __name__ == "__main__":
    main()
