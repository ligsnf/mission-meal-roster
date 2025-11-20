import csv
import argparse
from collections import defaultdict, Counter
from typing import List, Dict, Tuple, Optional, Set
import random

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
        
        # Initial capacities (we'll reset these for backtracking)
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
        
        # Determine assignment order: gender-restricted nights first
        ordered_nights = []
        for wd in NIGHTS:
            if wd in GENDER_ONLY:
                ordered_nights.insert(0, wd)  # Prioritize
            else:
                ordered_nights.append(wd)
        
        # But actually, let's keep natural order for simplicity
        # The key is backtracking will fix mistakes
        ordered_nights = NIGHTS
        
        week_day = ordered_nights[night_idx]
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
        print("STARTING ROSTER BUILD (with backtracking)")
        print("="*60 + "\n")
        
        success = self.solve_with_backtracking()
        
        if not success:
            return None, "No valid roster found (exhausted all possibilities)"
        
        print(f"\n✓ Solution found!")
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
        print("="*60 + "\n")
        
        return self.roster, "ok"


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


def main():
    parser = argparse.ArgumentParser(description="Build meal roster with backtracking.")
    parser.add_argument("--csv", required=True, help="Path to CSV")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for candidate ordering")
    parser.add_argument("--verbose", action="store_true", help="Enable detailed logging")
    args = parser.parse_args()

    random.seed(args.seed)
    
    people = read_csv(args.csv)
    err = validate_totals(people)
    if err:
        print("INPUT VALIDATION ERROR:", err)
        return

    builder = RosterBuilder(people)
    builder.verbose = args.verbose
    roster, status = builder.build()
    
    if roster is None:
        print(f"\n❌ BUILD FAILED: {status}")
        return

    print_roster(roster)
    summary = summarize(roster)
    print_summary(summary, people)


if __name__ == "__main__":
    main()