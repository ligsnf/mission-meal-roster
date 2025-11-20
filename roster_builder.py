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
        
        # Initialize capacities
        self.caps = {
            p["name"]: {
                "H": p["H"],
                "S": p["S"],
                "C": p["C"],
                "can_head": p["can_head"],
            }
            for p in people
        }
        
        # Roster structure
        self.roster: Dict[Tuple[int, str], Dict[str, str]] = {}
        
        # Tracking for back-to-back avoidance
        self.night_index = {NIGHTS[i]: i for i in range(len(NIGHTS))}
        self.last_role_for_person: Dict[str, Optional[Tuple[int, str]]] = {p: None for p in self.persons}
        
        # Debug mode
        self.verbose = True

    def log(self, msg: str, level=1):
        """Print with indentation based on level"""
        if self.verbose:
            print("  " * level + msg)

    def get_eligible_people(self, week_day: Tuple[int, str]) -> List[str]:
        """Get people eligible for this night based on gender constraints"""
        rule = GENDER_ONLY.get(week_day)
        if not rule:
            return self.persons.copy()
        return [p for p in self.persons if self.name_to_gender[p] == rule]

    def get_cap_key(self, role: str) -> str:
        """Map role to capacity key"""
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
        
        # Filter to available people
        candidates = [p for p in self.persons if self.is_available(p, role, week_day)]
        
        # Sort by:
        # 1. Remaining capacity in this category (lowest first - people who MUST use it)
        # 2. Whether they did same role type recently (penalize)
        # 3. Random tiebreaker
        def sort_key(person):
            remaining = self.caps[person][cap_key]
            
            # Penalty for back-to-back same role type
            penalty = 0
            last_night = self.last_role_for_person[person]
            if last_night is not None:
                curr_idx = self.night_index[week_day]
                last_idx = self.night_index[last_night]
                if curr_idx == last_idx + 1:
                    # Consecutive nights - check if same role type
                    last_assigned_role = None
                    for r, p in self.roster[last_night].items():
                        if p == person:
                            last_assigned_role = r
                            break
                    if last_assigned_role:
                        last_cap_key = self.get_cap_key(last_assigned_role)
                        if last_cap_key == cap_key:
                            penalty = 10  # Push down but don't exclude
            
            return (remaining + penalty, random.random())
        
        candidates.sort(key=sort_key)
        return candidates

    def assign_role(self, person: str, role: str, week_day: Tuple[int, str]):
        """Assign a person to a role"""
        cap_key = self.get_cap_key(role)
        
        if week_day not in self.roster:
            self.roster[week_day] = {}
        
        self.roster[week_day][role] = person
        self.caps[person][cap_key] -= 1
        self.last_role_for_person[person] = week_day
        
        self.log(f"✓ Assigned {person} to {role} (remaining {cap_key}={self.caps[person][cap_key]})", level=3)

    def assign_night(self, week_day: Tuple[int, str]) -> bool:
        """Try to assign all roles for one night"""
        week, day = week_day
        gender_tag = ""
        if week_day in GENDER_ONLY:
            gender_tag = f" ({'Girls' if GENDER_ONLY[week_day]=='F' else 'Boys'}-only)"
        
        self.log(f"Assigning Week {week} {day}{gender_tag}", level=1)
        
        eligible = self.get_eligible_people(week_day)
        self.log(f"Eligible people: {', '.join(eligible)}", level=2)
        
        if len(eligible) < 6:
            self.log(f"✗ Only {len(eligible)} eligible people, need 6!", level=2)
            return False
        
        # Try to assign each role
        for role in ROLES_PER_NIGHT:
            candidates = self.get_candidates(role, week_day)
            
            if not candidates:
                self.log(f"✗ No candidates for {role}", level=2)
                self.print_debug_state(week_day, role)
                return False
            
            # Assign the best candidate
            self.assign_role(candidates[0], role, week_day)
        
        # Verify 6 unique people
        assigned = set(self.roster[week_day].values())
        if len(assigned) != 6:
            self.log(f"✗ ERROR: Only {len(assigned)} unique people assigned!", level=2)
            return False
        
        return True

    def print_debug_state(self, failed_night: Tuple[int, str], failed_role: str):
        """Print detailed debug info when assignment fails"""
        print("\n" + "="*60)
        print("FAILURE DEBUG INFO")
        print("="*60)
        print(f"Failed on: Week {failed_night[0]} {failed_night[1]}, Role: {failed_role}")
        
        print("\nAlready assigned this night:")
        if failed_night in self.roster:
            for r, p in self.roster[failed_night].items():
                print(f"  {r}: {p}")
        else:
            print("  (none yet)")
        
        print("\nRemaining capacities:")
        cap_key = self.get_cap_key(failed_role)
        for person in sorted(self.persons):
            h, s, c = self.caps[person]["H"], self.caps[person]["S"], self.caps[person]["C"]
            total = h + s + c
            marker = ""
            if person in self.roster.get(failed_night, {}).values():
                marker = " [ALREADY ASSIGNED TONIGHT]"
            elif self.caps[person][cap_key] > 0:
                marker = f" [HAS {cap_key} CAPACITY]"
            print(f"  {person}: H={h}, S={s}, C={c}, Total={total}{marker}")
        
        print("\nGender constraint:")
        if failed_night in GENDER_ONLY:
            required = GENDER_ONLY[failed_night]
            print(f"  Required: {required}")
            eligible = [p for p in self.persons if self.name_to_gender[p] == required]
            print(f"  Eligible: {', '.join(eligible)}")
        else:
            print("  No restriction")
        
        print("="*60 + "\n")

    def build(self) -> Tuple[Optional[Dict], str]:
        """Main build function with phased approach"""
        print("\n" + "="*60)
        print("STARTING ROSTER BUILD")
        print("="*60 + "\n")
        
        # PHASE 1: Assign gender-restricted nights first (most constrained)
        gender_nights = sorted([wd for wd in NIGHTS if wd in GENDER_ONLY])
        
        if gender_nights:
            print("PHASE 1: Gender-restricted nights")
            print("-" * 40)
            for night in gender_nights:
                if not self.assign_night(night):
                    return None, f"Failed to assign gender-restricted night {night}"
            print()
        
        # PHASE 2: Assign remaining nights
        remaining_nights = [wd for wd in NIGHTS if wd not in self.roster]
        
        print("PHASE 2: Remaining nights")
        print("-" * 40)
        for night in remaining_nights:
            if not self.assign_night(night):
                return None, f"Failed to assign night {night}"
        
        # PHASE 3: Verify all capacities are used
        print("\nPHASE 3: Verification")
        print("-" * 40)
        
        mismatches = []
        for person in self.persons:
            h, s, c = self.caps[person]["H"], self.caps[person]["S"], self.caps[person]["C"]
            if h != 0 or s != 0 or c != 0:
                mismatches.append(f"{person}: H={h}, S={s}, C={c} remaining")
        
        if mismatches:
            print("✗ Capacity mismatches:")
            for m in mismatches:
                print(f"  {m}")
            return None, "Not all capacities were used"
        
        print("✓ All capacities used correctly")
        print("\n" + "="*60)
        print("BUILD SUCCESSFUL")
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
    
    # Create desired dict for comparison
    desired = {p["name"]: {"H": p["H"], "S": p["S"], "C": p["C"]} for p in people}
    
    print(f"{'Name':<6} {'Head':<6} {'Sous':<6} {'Clean':<6} {'Total':<6} {'Match'}")
    print("-" * 60)
    
    mismatches = []
    for person in sorted(summary):
        cnt = summary[person]
        h, s, c = cnt["H"], cnt["S"], cnt["C"]
        total = h + s + c
        
        # Check if matches desired
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
    parser = argparse.ArgumentParser(description="Build meal roster from desired counts.")
    parser.add_argument("--csv", required=True, help="Path to CSV")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for tiebreaking")
    args = parser.parse_args()

    random.seed(args.seed)
    
    people = read_csv(args.csv)
    err = validate_totals(people)
    if err:
        print("INPUT VALIDATION ERROR:", err)
        return

    builder = RosterBuilder(people)
    roster, status = builder.build()
    
    if roster is None:
        print(f"\n❌ BUILD FAILED: {status}")
        return

    print_roster(roster)
    summary = summarize(roster)
    print_summary(summary, people)


if __name__ == "__main__":
    main()