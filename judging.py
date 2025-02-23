import click
import pandas as pd
import glob
import os
from typing import List, Tuple
from tabulate import tabulate

# Configurable weights for different judging criteria
CRITERIA_WEIGHTS = {
    'design': 0.20,
    'originality': 0.20,
    'impact': 0.25,
    'technical': 0.35
}

class ScoreValidationError(Exception):
    pass

def validate_scores(df: pd.DataFrame) -> Tuple[bool, List[str]]:
    """
    Validate that scores are within the 0-10 range
    Returns (is_valid, list_of_issues)
    """
    issues = []

    for criterion in CRITERIA_WEIGHTS.keys():
        # Convert to numeric, keeping NaN
        scores = pd.to_numeric(df[criterion], errors='coerce')

        # Check for scores outside 0-10 range
        invalid_scores = scores[(scores < 0) | (scores > 10)].index
        if len(invalid_scores) > 0:
            for idx in invalid_scores:
                judge = df.loc[idx, 'judge']
                team = df.loc[idx, 'team number']
                score = df.loc[idx, criterion]
                issues.append(
                    f"Invalid {criterion} score ({score}) for Team {team} "
                    f"in review by {judge}"
                )

    return len(issues) == 0, issues

def validate_review_counts(df: pd.DataFrame, min_reviews: int) -> Tuple[bool, List[str]]:
    """
    Validate that all teams have at least min_reviews reviews
    Returns (is_valid, list_of_issues)
    """
    review_counts = df.groupby('team number').agg({
        'judge': 'count',
        'team name': 'first'
    })

    issues = []
    for team_num, row in review_counts.iterrows():
        if row['judge'] < min_reviews:
            issues.append(
                f"Team {team_num} ({row['team name']}) has only {row['judge']} "
                f"reviews, minimum required is {min_reviews}"
            )

    return len(issues) == 0, issues

def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize column names by removing (/10) and converting to lowercase
    """
    df.columns = [col.replace(' (/10)', '').strip().lower() for col in df.columns]
    return df

def load_and_combine_csvs(folder_path: str, min_reviews: int) -> pd.DataFrame:
    """
    Load all CSV files from a folder and combine them into a single DataFrame
    """
    all_files = glob.glob(os.path.join(folder_path, "*.csv"))
    if not all_files:
        raise click.ClickException(f"No CSV files found in {folder_path}")

    dfs = []
    for filename in all_files:
        try:
            df = pd.read_csv(filename, skiprows=[1])
            df = df.dropna(how='all')
            df = normalize_column_names(df)

            # Validate that a judge does not store a team more than once
            if df['team number'].duplicated().any():
                # print out the duplicated rows and the file name
                duplicated_rows = df[df['team number'].duplicated()]
                click.echo(f"Duplicated rows in {filename}:")
                click.echo(duplicated_rows)
                if not click.confirm("\nContinue despite duplicate team IDs?"):
                    raise click.ClickException("Aborting due to duplicate team IDs")


            judge_name = os.path.basename(filename).replace('.csv', '')
            df['judge'] = judge_name
            dfs.append(df)
        except Exception as e:
            click.echo(f"Warning: Could not process {filename}: {str(e)}")

    if not dfs:
        raise click.ClickException("No valid data found in CSV files")

    combined_df = pd.concat(dfs, ignore_index=True)
    combined_df = combined_df.dropna(subset=['team number'])

    # Validate scores
    scores_valid, score_issues = validate_scores(combined_df)
    if not scores_valid:
        click.echo("\n⚠️ Score Validation Issues:")
        for issue in score_issues:
            click.echo(f"  • {issue}")
        if not click.confirm("\nContinue despite score validation issues?"):
            raise click.ClickException("Aborting due to score validation issues")

    # Validate review counts
    reviews_valid, review_issues = validate_review_counts(combined_df, min_reviews)
    if not reviews_valid:
        click.echo("\n⚠️ Review Count Issues:")
        for issue in review_issues:
            click.echo(f"  • {issue}")
        if not click.confirm("\nContinue despite insufficient reviews?"):
            raise click.ClickException("Aborting due to insufficient reviews")

    return combined_df

def calculate_team_stats(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate team statistics including number of reviews and weighted scores
    """
    # Convert score columns to numeric
    for criterion in CRITERIA_WEIGHTS.keys():
        df[criterion] = pd.to_numeric(df[criterion], errors='coerce')

    # Calculate weighted scores for each review
    for criterion, weight in CRITERIA_WEIGHTS.items():
        df[f'{criterion}_weighted'] = df[criterion] * weight

    # Calculate total weighted score for each review
    df['total_weighted'] = sum(df[f'{criterion}_weighted'] for criterion in CRITERIA_WEIGHTS.keys())

    # Group by team to get statistics
    team_stats = df.groupby(['team number', 'team name']).agg({
        'judge': 'count',  # Number of reviews
        'total_weighted': 'sum',  # Sum of weighted scores
        **{criterion: 'mean' for criterion in CRITERIA_WEIGHTS.keys()}  # Average raw scores
    }).reset_index()

    # Rename columns
    team_stats = team_stats.rename(columns={'judge': 'num_reviews'})

    # Calculate final score (total weighted sum divided by number of reviews)
    team_stats['final_score'] = team_stats['total_weighted'] / team_stats['num_reviews']

    # Sort by final score
    team_stats = team_stats.sort_values('final_score', ascending=False)

    return team_stats

def format_results(results: pd.DataFrame, top: int) -> str:
    """
    Format results into a nice ASCII table
    """
    display_cols = [
        'team number', 'team name', 'num_reviews', 'final_score',
        *CRITERIA_WEIGHTS.keys()
    ]

    display_df = results[display_cols].head(top)

    column_names = {
        'team number': 'Team #',
        'team name': 'Team Name',
        'num_reviews': '# Reviews',
        'final_score': 'Final Score',
        'design': 'Design',
        'originality': 'Originality',
        'impact': 'Impact',
        'technical': 'Technical'
    }
    display_df = display_df.rename(columns=column_names)

    # Format numeric columns
    display_df['Final Score'] = display_df['Final Score'].round(2)
    for criterion in CRITERIA_WEIGHTS.keys():
        display_df[column_names[criterion]] = display_df[column_names[criterion]].round(2)

    return tabulate(
        display_df,
        headers='keys',
        tablefmt='fancy_grid',
        showindex=False
    )

@click.command()
@click.argument('folder_path', type=click.Path(exists=True))
@click.option('--top', '-t', default=3, help='Number of top teams to display')
@click.option('--min-reviews', '-m', default=2, help='Minimum number of reviews required per team')
@click.option('--output', '-o', type=click.Path(), help='Path to save results CSV')
def main(folder_path: str, top: int, min_reviews: int, output: str):
    """Process hackathon judging scores and determine winners"""
    click.echo(f"Processing CSV files from {folder_path}")

    try:
        click.echo("Loading and validating CSV files...")
        combined_df = load_and_combine_csvs(folder_path, min_reviews)

        click.echo("Calculating team scores...")
        results = calculate_team_stats(combined_df)

        click.echo("\n🏆 Hackathon Results 🏆")
        click.echo(format_results(results, top))

        if output:
            results.to_csv(output, index=False)
            click.echo(f"\nDetailed results saved to {output}")

    except Exception as e:
        raise click.ClickException(str(e))

if __name__ == '__main__':
    main()
