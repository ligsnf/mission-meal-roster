# Mission Meal Roster Generator

Automated roster builder for coordinating team meals during a mission trip to Nagoya, Japan.

## Overview

Generates a balanced meal roster for 12 team members across 4 weeks (16 cooking nights total).

**Roles per night:**
- 1× Head Chef
- 2× Sous Chef
- 3× Clean-up Crew

**Cooking days:** Monday, Tuesday, Thursday, Sunday

## Features

- Fair distribution across roles and people based on desired counts
- Gender-restricted nights (Week 2: Mon girls-only, Tue boys-only)
- Head chef capability constraints
- Avoids back-to-back identical role assignments
- Constraint-based algorithm with phased assignment

## Usage

```bash
python roster_builder.py --csv desired_counts.csv --seed 42
```

Try different `--seed` values if assignment fails.

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

## Requirements

Python 3.7+ (standard library only)