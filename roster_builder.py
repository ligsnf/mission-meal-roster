import csv
import argparse
from collections import defaultdict, Counter
from typing import List, Dict, Tuple, Optional, Set
import random
import math

# Configuration
COOKING_DAYS = ["Mon", "Tue", "Thu", "Sun"]
WEEKS = [1, 2, 3, 4]
NIGHTS = [(w, d) for w in WEEKS for d in COOKING_DAYS]
ROLES_PER_NIGHT = ["H", "S1", "S2", "C1", "C2", "C3"]
TOTAL_HEAD = len(NIGHTS)
TOTAL_SOUS = len(NIGHTS) * 2
TOTAL_CLEAN = len(NIGHTS) * 3

GENDER_ONLY = {
    (2, "Mon"): "F",  # Girls-only
    (2, "Tue"): "M",  # Boys-only
}


def read_csv(path: str):
    people = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            name = row["name"].strip()
            head = int(row["head"])
            sous = int(row["sous"])
            clean = int(row["clean"])
            can_head = int(row.get("can_head", "1"))
            gender = row.get("gender", "").strip().upper() or None
            people.append(
                {
                    "name": name,
                    "H": head,
                    "S": sous,
                    "C": clean,
                    "can_head": bool(can_head),
                    "gender": gender,
                }
            )
    return people


def validate_totals(people: List[Dict]) -> Optional[str]:
    sum_h = sum(p["H"] for p in people)
    sum_s = sum(p["S"] for p in people)
    sum_c = sum(p["C"] for p in people)

    if sum_h != TOTAL_HEAD:
        return f"Invalid total Heads: got {sum_h}, expected {TOTAL_HEAD}"
    if sum_s != TOTAL_SOUS:
        return f"Invalid total Sous: got {sum_s}, expected {TOTAL_SOUS}"
    if sum_c != TOTAL_CLEAN:
        return f"Invalid total Cleans: got {sum_c}, expected {TOTAL_CLEAN}"
    return None


class RosterBuilder:
    def __init__(self, people: List[Dict]):
        self.people = people
        self.persons = [p["name"] for p in people]
        self.name_to_gender = {p["name"]: p["gender"] for p in people}
        
        # Initial capacities
        self.initial_caps = {
            p["name"]: {
                "H": p["H"],
                "S": p["S"],
                "C": p["C"],
                "can_head": p["can_head"],
            }
            for p in people
        }
        
        # Working capacities
        self.caps = {}
        self.reset_caps()
        
        # Roster structure
        self.roster: Dict[Tuple[int, str], Dict[str, str]] = {}
        
        # Backtracking state
        self.assignment_history: List[Tuple[Tuple[int, str], str, str]] = []  # (night, role, person)
        self.tried_candidates: Dict[Tuple[Tuple[int, str], str], Set[str]] = {}  # (night, role) -> set of tried people
        
        # Stats
        self.backtrack_count = 0
        self.assignment_count = 0
        
        # Night index for scoring
        self.night_index = {NIGHTS[i]: i for i in range(len(NIGHTS))}
        
        # Debug
        self.verbose = False

    def reset_caps(self):
        """Reset capacities to initial values"""
        self.caps = {
            name: {
                "H": self.initial_caps[name]["H"],
                "S": self.initial_caps[name]["S"],
                "C": self.initial_caps[name]["C"],
                "can_head": self.initial_caps[name]["can_head"],
            }
            for name in self.persons
        }

    def log(self, msg: str, level=1):
        if self.verbose:
            print("  " * level + msg)

    def get_cap_key(self, role: str) -> str:
        if role == "H":
            return "H"
        elif role.startswith("S"):
            return "S"
        else:
            return "C"

    def is_available(self, person: str, role: str, week_day: Tuple[int, str]) -> bool:
        """Check if person can be assigned this role on this night"""
        # Already assigned this night?
        if person in self.roster.get(week_day, {}).values():
            return False
        
        # Has capacity?
        cap_key = self.get_cap_key(role)
        if self.caps[person][cap_key] <= 0:
            return False
        
        # Can be head chef?
        if role == "H" and not self.caps[person]["can_head"]:
            return False
        
        # Gender restriction?
        rule = GENDER_ONLY.get(week_day)
        if rule and self.name_to_gender[person] != rule:
            return False
        
        return True

    def get_candidates(self, role: str, week_day: Tuple[int, str]) -> List[str]:
        """Get sorted list of candidates for this role"""
        cap_key = self.get_cap_key(role)
        
        # Filter to available people who haven't been tried yet for this slot
        slot_key = (week_day, role)
        tried = self.tried_candidates.get(slot_key, set())
        
        candidates = [
            p for p in self.persons 
            if self.is_available(p, role, week_day) and p not in tried
        ]
        
        # Sort by remaining capacity (lowest first) + random tiebreaker
        candidates.sort(key=lambda p: (self.caps[p][cap_key], random.random()))
        return candidates

    def assign_role(self, person: str, role: str, week_day: Tuple[int, str]):
        """Assign a person to a role"""
        cap_key = self.get_cap_key(role)
        
        if week_day not in self.roster:
            self.roster[week_day] = {}
        
        self.roster[week_day][role] = person
        self.caps[person][cap_key] -= 1
        self.assignment_history.append((week_day, role, person))
        self.assignment_count += 1
        
        # Mark this person as tried for this slot
        slot_key = (week_day, role)
        if slot_key not in self.tried_candidates:
            self.tried_candidates[slot_key] = set()
        self.tried_candidates[slot_key].add(person)
        
        self.log(f"✓ Assigned {person} to {role} (remaining {cap_key}={self.caps[person][cap_key]})", level=3)

    def undo_assignment(self):
        """Undo the most recent assignment"""
        if not self.assignment_history:
            return False
        
        week_day, role, person = self.assignment_history.pop()
        cap_key = self.get_cap_key(role)
        
        # Restore capacity
        self.caps[person][cap_key] += 1
        
        # Remove from roster
        del self.roster[week_day][role]
        if not self.roster[week_day]:
            del self.roster[week_day]
        
        self.backtrack_count += 1
        self.log(f"⟲ Backtracked {person} from {role} on {week_day}", level=3)
        
        return True

    def solve_with_backtracking(self) -> bool:
        """Recursively solve the roster with backtracking"""
        # Base case: all nights assigned
        if len(self.assignment_history) == len(NIGHTS) * len(ROLES_PER_NIGHT):
            return True
        
        # Determine current night and role
        num_assigned = len(self.assignment_history)
        night_idx = num_assigned // len(ROLES_PER_NIGHT)
        role_idx = num_assigned % len(ROLES_PER_NIGHT)
        
        week_day = NIGHTS[night_idx]
        role = ROLES_PER_NIGHT[role_idx]
        
        # Get candidates for this slot
        candidates = self.get_candidates(role, week_day)
        
        if not candidates:
            # Dead end - need to backtrack
            return False
        
        # Try each candidate
        for person in candidates:
            self.assign_role(person, role, week_day)
            
            # Recursively try to complete the rest
            if self.solve_with_backtracking():
                return True
            
            # Failed - undo and try next candidate
            self.undo_assignment()
        
        # Exhausted all candidates for this slot - backtrack further
        # Clear tried candidates for this slot so future attempts can retry
        slot_key = (week_day, role)
        self.tried_candidates.pop(slot_key, None)
        
        return False

    def build(self) -> Tuple[Optional[Dict], str]:
        """Main build function with backtracking"""
        print("\n" + "="*60)
        print("PHASE 1: Finding valid roster (backtracking)")
        print("="*60 + "\n")
        
        success = self.solve_with_backtracking()
        
        if not success:
            return None, "No valid roster found (exhausted all possibilities)"
        
        print(f"✓ Valid solution found!")
        print(f"  Assignments: {self.assignment_count}")
        print(f"  Backtracks: {self.backtrack_count}")
        
        # Verify all capacities used
        mismatches = []
        for person in self.persons:
            h, s, c = self.caps[person]["H"], self.caps[person]["S"], self.caps[person]["C"]
            if h != 0 or s != 0 or c != 0:
                mismatches.append(f"{person}: H={h}, S={s}, C={c} remaining")
        
        if mismatches:
            print("\n✗ Capacity mismatches:")
            for m in mismatches:
                print(f"  {m}")
            return None, "Not all capacities were used"
        
        print("✓ All capacities used correctly")
        
        return self.roster, "ok"


class RosterOptimizer:
    def __init__(self, roster: Dict, people: List[Dict]):
        self.roster = roster
        self.people = people
        self.persons = [p["name"] for p in people]
        self.name_to_gender = {p["name"]: p["gender"] for p in people}
        self.name_to_can_head = {p["name"]: p["can_head"] for p in people}
        self.night_index = {NIGHTS[i]: i for i in range(len(NIGHTS))}
        
    def get_cap_key(self, role: str) -> str:
        if role == "H":
            return "H"
        elif role.startswith("S"):
            return "S"
        else:
            return "C"
    
    def calculate_score(self, roster: Dict) -> float:
        """
        Calculate distribution score. Lower = better.
        
        Penalizes:
        - Uneven distribution across weeks
        - Back-to-back same role type
        - Clustering within short time periods
        """
        score = 0.0
        
        # 1. Week distribution variance (weight: 10)
        person_weeks = defaultdict(lambda: [0, 0, 0, 0])
        for (week, day), roles in roster.items():
            for role, person in roles.items():
                person_weeks[person][week - 1] += 1
        
        for person, counts in person_weeks.items():
            mean = sum(counts) / 4
            variance = sum((c - mean) ** 2 for c in counts)
            score += variance * 10
        
        # 2. Back-to-back same role type penalty (weight: 5)
        person_nights = defaultdict(list)
        for night, roles in sorted(roster.items(), key=lambda x: self.night_index[x[0]]):
            for role, person in roles.items():
                person_nights[person].append((self.night_index[night], self.get_cap_key(role)))
        
        for person, assignments in person_nights.items():
            assignments.sort()  # Sort by night index
            for i in range(len(assignments) - 1):
                idx1, role1 = assignments[i]
                idx2, role2 = assignments[i + 1]
                # Check if consecutive cooking nights with same role type
                if idx2 == idx1 + 1 and role1 == role2:
                    score += 5
        
        # 3. Clustering penalty - prefer spread throughout the month (weight: 2)
        for person in self.persons:
            night_indices = []
            for night, roles in roster.items():
                if person in roles.values():
                    night_indices.append(self.night_index[night])
            
            night_indices.sort()
            # Calculate gaps between assignments
            if len(night_indices) > 1:
                gaps = [night_indices[i+1] - night_indices[i] for i in range(len(night_indices)-1)]
                gap_variance = sum((g - sum(gaps)/len(gaps))**2 for g in gaps) / len(gaps)
                score += gap_variance * 2
        
        return score
    
    def can_swap(self, roster: Dict, night1: Tuple, role1: str, night2: Tuple, role2: str) -> bool:
        """Check if two assignments can be swapped"""
        person1 = roster[night1][role1]
        person2 = roster[night2][role2]
        
        # Can't swap with yourself
        if person1 == person2:
            return False
        
        # Check if person1 can do role2 on night2
        if role2 == "H" and not self.name_to_can_head[person1]:
            return False
        
        gender_rule2 = GENDER_ONLY.get(night2)
        if gender_rule2 and self.name_to_gender[person1] != gender_rule2:
            return False
        
        # Same role type check
        if self.get_cap_key(role1) != self.get_cap_key(role2):
            return False
        
        # Check if person2 can do role1 on night1
        if role1 == "H" and not self.name_to_can_head[person2]:
            return False
        
        gender_rule1 = GENDER_ONLY.get(night1)
        if gender_rule1 and self.name_to_gender[person2] != gender_rule1:
            return False
        
        # Check neither person is already on the other night
        if person1 in roster[night2].values():
            return False
        if person2 in roster[night1].values():
            return False
        
        return True
    
    def perform_swap(self, night1: Tuple, role1: str, night2: Tuple, role2: str, roster: Dict):
        """Perform a swap in the given roster"""
        person1 = roster[night1][role1]
        person2 = roster[night2][role2]
        
        roster[night1][role1] = person2
        roster[night2][role2] = person1
    
    def optimize(self, iterations: int = 5000, initial_temp: float = 10.0, 
                 cooling_rate: float = 0.95) -> Dict:
        """Optimize roster using simulated annealing"""
        print("\n" + "="*60)
        print("PHASE 2: Optimizing distribution (simulated annealing)")
        print("="*60 + "\n")
        
        import copy
        
        current_roster = copy.deepcopy(self.roster)
        current_score = self.calculate_score(current_roster)
        best_roster = copy.deepcopy(current_roster)
        best_score = current_score
        
        temperature = initial_temp
        accepts = 0
        improves = 0
        
        # Get all possible swap pairs
        all_assignments = []
        for night, roles in self.roster.items():
            for role in roles:
                all_assignments.append((night, role))
        
        print(f"Initial score: {current_score:.2f}")
        print(f"Temperature: {initial_temp} → 0 (cooling rate: {cooling_rate})")
        print(f"Iterations: {iterations}\n")
        
        for i in range(iterations):
            # Pick two random assignments
            (night1, role1), (night2, role2) = random.sample(all_assignments, 2)
            
            # Check if swap is valid
            if not self.can_swap(current_roster, night1, role1, night2, role2):
                continue
            
            # Make swap
            test_roster = copy.deepcopy(current_roster)
            self.perform_swap(night1, role1, night2, role2, test_roster)
            
            # Calculate new score
            new_score = self.calculate_score(test_roster)
            delta = new_score - current_score
            
            # Decide whether to accept
            accept = False
            if delta < 0:
                # Improvement - always accept
                accept = True
                improves += 1
            elif temperature > 0:
                # Worse solution - accept with probability
                probability = math.exp(-delta / temperature)
                if random.random() < probability:
                    accept = True
            
            if accept:
                current_roster = test_roster
                current_score = new_score
                accepts += 1
                
                # Track best
                if current_score < best_score:
                    best_roster = copy.deepcopy(current_roster)
                    best_score = current_score
            
            # Cool down
            temperature *= cooling_rate
            
            # Progress update
            if (i + 1) % 1000 == 0:
                print(f"  Iteration {i+1:5d}: score={current_score:.2f}, best={best_score:.2f}, "
                      f"temp={temperature:.3f}, accepts={accepts}, improves={improves}")
        
        print(f"\n✓ Optimization complete!")
        print(f"  Initial score: {self.calculate_score(self.roster):.2f}")
        print(f"  Final score:   {best_score:.2f}")
        print(f"  Improvement:   {((self.calculate_score(self.roster) - best_score) / self.calculate_score(self.roster) * 100):.1f}%")
        print(f"  Swaps accepted: {accepts}/{iterations} ({accepts/iterations*100:.1f}%)")
        print(f"  Improvements: {improves}")
        
        return best_roster


def summarize(roster: Dict[Tuple[int, str], Dict[str, str]]) -> Dict[str, Counter]:
    per = defaultdict(Counter)
    for wd, roles in roster.items():
        for role, person in roles.items():
            per[person][role] += 1
    
    summary = {}
    for person, cnt in per.items():
        h = cnt.get("H", 0)
        s = cnt.get("S1", 0) + cnt.get("S2", 0)
        c = cnt.get("C1", 0) + cnt.get("C2", 0) + cnt.get("C3", 0)
        summary[person] = Counter({"H": h, "S": s, "C": c})
    return summary


def print_roster(roster: Dict[Tuple[int, str], Dict[str, str]]):
    print("\n" + "="*60)
    print("FINAL ROSTER")
    print("="*60 + "\n")
    
    for w in WEEKS:
        print(f"Week {w}")
        print("-" * 40)
        for d in COOKING_DAYS:
            wd = (w, d)
            if wd not in roster:
                continue
            roles = roster[wd]
            
            gender_tag = ""
            if wd in GENDER_ONLY:
                gender_tag = f" ({'Girls' if GENDER_ONLY[wd]=='F' else 'Boys'}-only)"
            
            print(f"  {d:3} {gender_tag}")
            print(f"      Head: {roles['H']}")
            print(f"      Sous: {roles['S1']}, {roles['S2']}")
            print(f"      Clean: {roles['C1']}, {roles['C2']}, {roles['C3']}")
        print()


def print_summary(summary: Dict[str, Counter], people: List[Dict]):
    print("\n" + "="*60)
    print("PER-PERSON SUMMARY")
    print("="*60 + "\n")
    
    desired = {p["name"]: {"H": p["H"], "S": p["S"], "C": p["C"]} for p in people}
    
    print(f"{'Name':<6} {'Head':<6} {'Sous':<6} {'Clean':<6} {'Total':<6} {'Match'}")
    print("-" * 60)
    
    mismatches = []
    for person in sorted(summary):
        cnt = summary[person]
        h, s, c = cnt["H"], cnt["S"], cnt["C"]
        total = h + s + c
        
        match = "✓"
        if (h != desired[person]["H"] or 
            s != desired[person]["S"] or 
            c != desired[person]["C"]):
            match = "✗"
            mismatches.append(person)
        
        print(f"{person:<6} {h:<6} {s:<6} {c:<6} {total:<6} {match}")
    
    if mismatches:
        print("\n⚠ Mismatches detected for: " + ", ".join(mismatches))
    else:
        print("\n✓ All assignments match desired counts!")


def print_distribution_analysis(roster: Dict):
    """Print week-by-week distribution for each person"""
    print("\n" + "="*60)
    print("DISTRIBUTION ANALYSIS")
    print("="*60 + "\n")
    
    person_weeks = defaultdict(lambda: [0, 0, 0, 0])
    for (week, day), roles in roster.items():
        for role, person in roles.items():
            person_weeks[person][week - 1] += 1
    
    print(f"{'Name':<6} {'W1':<4} {'W2':<4} {'W3':<4} {'W4':<4} {'Variance'}")
    print("-" * 60)
    
    for person in sorted(person_weeks.keys()):
        counts = person_weeks[person]
        mean = sum(counts) / 4
        variance = sum((c - mean) ** 2 for c in counts) / 4
        
        print(f"{person:<6} {counts[0]:<4} {counts[1]:<4} {counts[2]:<4} {counts[3]:<4} {variance:.2f}")
    
    avg_variance = sum(
        sum((c - sum(counts)/4) ** 2 for c in counts) / 4
        for counts in person_weeks.values()
    ) / len(person_weeks)
    
    print(f"\nAverage variance: {avg_variance:.2f} (lower = more even distribution)")


def main():
    parser = argparse.ArgumentParser(description="Build and optimize meal roster.")
    parser.add_argument("--csv", required=True, help="Path to CSV")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--no-optimize", action="store_true", help="Skip optimization phase")
    parser.add_argument("--iterations", type=int, default=5000, help="Optimization iterations")
    parser.add_argument("--temp", type=float, default=10.0, help="Initial temperature")
    parser.add_argument("--cooling", type=float, default=0.95, help="Cooling rate")
    parser.add_argument("--verbose", action="store_true", help="Detailed logging")
    args = parser.parse_args()

    random.seed(args.seed)
    
    people = read_csv(args.csv)
    err = validate_totals(people)
    if err:
        print("INPUT VALIDATION ERROR:", err)
        return

    # Phase 1: Find valid roster
    builder = RosterBuilder(people)
    builder.verbose = args.verbose
    roster, status = builder.build()
    
    if roster is None:
        print(f"\n❌ BUILD FAILED: {status}")
        return
    
    # Phase 2: Optimize distribution
    if not args.no_optimize:
        optimizer = RosterOptimizer(roster, people)
        roster = optimizer.optimize(
            iterations=args.iterations,
            initial_temp=args.temp,
            cooling_rate=args.cooling
        )

    print_roster(roster)
    summary = summarize(roster)
    print_summary(summary, people)
    print_distribution_analysis(roster)


if __name__ == "__main__":
    main()