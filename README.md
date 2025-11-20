# Mission Meal Roster Generator

Automated roster generator for mission trip meal coordination - fair distribution across head chef, sous chef, and cleanup roles

## Overview

Generates a balanced meal roster for 12 team members across 4 weeks (16 cooking nights total) using constraint-based backtracking and simulated annealing optimization.

**Roles per night:**
- 1× Head Chef
- 2× Sous Chef
- 3× Clean-up Crew

**Cooking days:** Monday, Tuesday, Thursday, Sunday

## Features

- Constraint-based solver with backtracking
- Simulated annealing optimization for even distribution
- Gender-restricted nights (Week 2: Mon girls-only, Tue boys-only)
- Head chef capability constraints
- Minimizes back-to-back same role assignments
- Balanced distribution across weeks
- CSV export for easy sharing

## Usage

Basic usage:
```bash
python roster_builder.py --csv desired_counts.csv
```

Export to CSV:
```bash
python roster_builder.py --csv desired_counts.csv --export roster_output.csv
```

Custom optimization parameters:
```bash
python roster_builder.py --csv desired_counts.csv --iterations 10000 --temp 15.0
```

Skip optimization (faster, less balanced):
```bash
python roster_builder.py --csv desired_counts.csv --no-optimize
```

## Options

- `--csv`: Path to input CSV (required)
- `--seed`: Random seed for reproducibility (default: 42)
- `--export`: Export roster to CSV file
- `--no-optimize`: Skip simulated annealing phase
- `--iterations`: Optimization iterations (default: 5000)
- `--temp`: Initial temperature for annealing (default: 10.0)
- `--cooling`: Cooling rate (default: 0.95)
- `--verbose`: Show detailed logging

## CSV Format

```csv
name,head,sous,clean,can_head,gender
AS,2,2,4,1,M
EG,1,3,4,1,F
ET,0,4,4,0,M
```

**Columns:**
- `name`: Person's initials
- `head`: Number of head chef duties
- `sous`: Number of sous chef duties  
- `clean`: Number of cleanup duties
- `can_head`: 1 if confident as head chef, 0 otherwise
- `gender`: M or F (for gender-restricted nights)

**Totals must equal:** 16 head, 32 sous, 48 clean

## How It Works

1. **Phase 1 - Backtracking Solver**: Finds a valid roster satisfying all hard constraints
2. **Phase 2 - Simulated Annealing**: Optimizes distribution across weeks and minimizes clustering

## Requirements

Python 3.7+ (standard library only)