# Hack Canada's Judging Normalization Script

This script is used to normalize the judging scores for the Hack Canada hackathon.

## Usage
1. Clone this repository to your local machine.
2. Install [uv](https://docs.astral.sh/uv/getting-started/installation/)
3. Run `uv sync` to install the dependencies.
4. Place your judging CSV files in a csv folder. The script will automatically detect the CSV files in the folder.
5. Run `uv run judging.py <path_to_csv_folder>` to normalize the judging scores.

## Configuration
The script uses a configurable weighting system to calculate the final judging score.
The weights are defined in the `CRITERIA_WEIGHTS` dictionary in the `judging.py` file.
You can modify these weights to adjust the relative importance of different criteria.

The script also validates the scores to ensure they are within the 0-10 range.
If a score is outside this range, it will be ignored and a warning will be displayed.

### CSV Format
The CSV files should be in the following format:
```
| Team Number | Team Name | Design (/10) | Originality (/10) | Impact (/10) | Technical (/10) | Notes/Comments |
```
## License
This script is licensed under the GNU General Public License v3.0.

## Disclaimer
This script is provided as-is and without warranty.

