import csv
import argparse
from collections import defaultdict, Counter
from typing import List, Dict, Tuple, Optional

# Configuration
COOKING_DAYS = ["Mon", "Tue", "Thu", "Sun"]  # per week
WEEKS = [1, 2, 3, 4]
NIGHTS = [(w, d) for w in WEEKS for d in COOKING_DAYS]  # 16 nights
ROLES_PER_NIGHT = ["H", "S1", "S2", "C1", "C2", "C3"]  # 6 slots per night
TOTAL_HEAD = len(NIGHTS)  # 16
TOTAL_SOUS = len(NIGHTS) * 2  # 32
TOTAL_CLEAN = len(NIGHTS) * 3  # 48

# Optional constraints
GENDER_ONLY = {
    # (week, day): "M" or "F"
    (2, "Mon"): "F",  # Girls-only
    (2, "Tue"): "M",  # Boys-only
}
# People not allowed to head (can also use can_head=0 in CSV)
BANNED_HEADS = set()  # e.g., {"ET"}

# Avoid same role on back-to-back cooking days: best-effort
AVOID_BACK_TO_BACK_SAME_ROLE = True


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
    total = sum_h + sum_s + sum_c

    if sum_h != TOTAL_HEAD:
        return f"Invalid total Heads: got {sum_h}, expected {TOTAL_HEAD}"
    if sum_s != TOTAL_SOUS:
        return f"Invalid total Sous: got {sum_s}, expected {TOTAL_SOUS}"
    if sum_c != TOTAL_CLEAN:
        return f"Invalid total Cleans: got {sum_c}, expected {TOTAL_CLEAN}"
    if total != len(NIGHTS) * len(ROLES_PER_NIGHT):
        return f"Invalid grand total: got {total}, expected {len(NIGHTS) * len(ROLES_PER_NIGHT)}"
    return None


def gender_ok(name_to_gender: Dict[str, Optional[str]], week_day: Tuple[int, str], person: str) -> bool:
    rule = GENDER_ONLY.get(week_day)
    if not rule:
        return True
    g = name_to_gender.get(person)
    return g == rule


def can_assign_head(person: str, person_caps: Dict[str, Dict]) -> bool:
    if person in BANNED_HEADS:
        return False
    return person_caps[person]["can_head"]


def build_roster(people: List[Dict]) -> Tuple[Optional[Dict], str]:
    # Prepare capacities
    persons = [p["name"] for p in people]
    name_to_gender = {p["name"]: p["gender"] for p in people}

    caps = {
        p["name"]: {
            "H": p["H"],
            "S": p["S"],
            "C": p["C"],
            "can_head": p["can_head"],
        }
        for p in people
    }

    # Pre-check: banned heads must have H=0
    for p in persons:
        if p in BANNED_HEADS and caps[p]["H"] != 0:
            return None, f"{p} is banned from Head but has H={caps[p]['H']} requested."

    # Roster data structure: {(week, day): {"H": name, "S1": name, ...}}
    roster: Dict[Tuple[int, str], Dict[str, str]] = {}
    # Track last role by person to help avoid back-to-back same role
    last_role_for_person: Dict[str, Optional[str]] = {p: None for p in persons}
    # Track last assignment day index to detect back-to-back cooking day
    night_index = {NIGHTS[i]: i for i in range(len(NIGHTS))}
    last_night_index_for_person: Dict[str, Optional[int]] = {p: None for p in persons}

    # Helper to pick candidate list for a role based on remaining caps and constraints
    def candidates_for_role(week_day: Tuple[int, str], role: str) -> List[str]:
        # Map role group: H uses "H" cap; S1/S2 use "S"; C1/C2/C3 use "C"
        cap_key = "H" if role == "H" else "S" if role.startswith("S") else "C"
        cands = []
        for person in persons:
            if caps[person][cap_key] <= 0:
                continue
            if role == "H" and not can_assign_head(person, caps):
                continue
            if not gender_ok(name_to_gender, week_day, person):
                continue
            # Back-to-back same role avoidance
            if AVOID_BACK_TO_BACK_SAME_ROLE:
                prev_idx = last_night_index_for_person[person]
                prev_role = last_role_for_person[person]
                curr_idx = night_index[week_day]
                if prev_idx is not None and curr_idx == prev_idx + 1:
                    # Avoid same cap group on consecutive cooking days
                    # Compare by cap group (H/S/C)
                    if (prev_role == "H" and cap_key == "H") or (
                        prev_role in ("S1", "S2") and cap_key == "S"
                    ) or (prev_role in ("C1", "C2", "C3") and cap_key == "C"):
                        # Penalize by lowering priority, but keep as possible
                        pass
            cands.append(person)
        # Sort candidates by least remaining cap in this category (use people who must fill it)
        cands.sort(key=lambda p: caps[p][cap_key])
        return cands

    # Assignment loop per night
    for wd in NIGHTS:
        roster[wd] = {}
        for role in ROLES_PER_NIGHT:
            cap_key = "H" if role == "H" else "S" if role.startswith("S") else "C"
            cands = candidates_for_role(wd, role)
            print(f"  Role {role} ({cap_key}): {len(cands)} candidates")
            print(f"    Already assigned tonight: {list(roster[wd].values())}")
            print(f"    Available: {[c for c in cands if c not in roster[wd].values()][:5]}")  # Show first 5
            if not cands:
                print(f"\n!!! FAILURE STATE !!!")
                print(f"Night: {wd}, Role: {role}")
                print(f"Already assigned: {roster[wd]}")
                print(f"Remaining capacities:")
                for p in persons:
                    if caps[p]["H"] + caps[p]["S"] + caps[p]["C"] > 0:
                        print(f"  {p}: H={caps[p]['H']}, S={caps[p]['S']}, C={caps[p]['C']}")
                return None, f"Cannot assign role {role} on {wd}; no candidates with remaining {cap_key} capacity and constraints."
            # Choose candidate prioritizing:
            # - Not same person already assigned this night
            # - Avoid back-to-back same cap group if possible
            assigned = None
            for person in cands:
                if person in roster[wd].values():
                    continue
                # If back-to-back and same cap group and we have other options, skip
                prev_idx = last_night_index_for_person[person]
                prev_role = last_role_for_person[person]
                curr_idx = night_index[wd]
                same_group_back_to_back = False
                if AVOID_BACK_TO_BACK_SAME_ROLE and prev_idx is not None and curr_idx == prev_idx + 1:
                    if (prev_role == "H" and cap_key == "H") or (
                        prev_role in ("S1", "S2") and cap_key == "S"
                    ) or (prev_role in ("C1", "C2", "C3") and cap_key == "C"):
                        same_group_back_to_back = True
                if same_group_back_to_back:
                    # try to avoid if others exist
                    continue
                assigned = person
                break
            # If we didn't find a non-back-to-back, pick the first viable
            if assigned is None:
                for person in cands:
                    if person in roster[wd].values():
                        continue
                    assigned = person
                    break
            if assigned is None:
                return None, f"Failed to assign role {role} on {wd} due to uniqueness constraint."

            roster[wd][role] = assigned
            caps[assigned][cap_key] -= 1
            last_role_for_person[assigned] = role
            last_night_index_for_person[assigned] = night_index[wd]

    # Final caps must all be zero
    leftover = {p: caps[p] for p in persons}
    for p in persons:
        if leftover[p]["H"] != 0 or leftover[p]["S"] != 0 or leftover[p]["C"] != 0:
            return None, f"Post-assignment mismatch for {p}: {leftover[p]} (non-zero remains)."

    return roster, "ok"


def summarize(roster: Dict[Tuple[int, str], Dict[str, str]]) -> Dict[str, Counter]:
    per = defaultdict(Counter)
    for wd, roles in roster.items():
        for role, person in roles.items():
            per[person][role] += 1
    # Aggregate S and C tallies
    summary = {}
    for person, cnt in per.items():
        h = cnt.get("H", 0)
        s = cnt.get("S1", 0) + cnt.get("S2", 0)
        c = cnt.get("C1", 0) + cnt.get("C2", 0) + cnt.get("C3", 0)
        summary[person] = Counter({"H": h, "S": s, "C": c})
    return summary


def print_roster(roster: Dict[Tuple[int, str], Dict[str, str]]):
    print("Final Roster:")
    for w in WEEKS:
        print(f"Week {w}")
        for d in COOKING_DAYS:
            wd = (w, d)
            if wd not in roster:
                continue
            roles = roster[wd]
            line = f"  {d}: H {roles['H']} | S1 {roles['S1']} | S2 {roles['S2']} | C1 {roles['C1']} | C2 {roles['C2']} | C3 {roles['C3']}"
            # Mark gender-only
            if wd in GENDER_ONLY:
                line += f"   ({'Girls-only' if GENDER_ONLY[wd]=='F' else 'Boys-only'})"
            print(line)
        print()


def print_summary(summary: Dict[str, Counter]):
    print("Per-person totals:")
    for person in sorted(summary):
        cnt = summary[person]
        print(f"  {person}: H {cnt['H']}, S {cnt['S']}, C {cnt['C']}, Total {cnt['H']+cnt['S']+cnt['C']}")


def main():
    parser = argparse.ArgumentParser(description="Build meal roster from desired counts.")
    parser.add_argument("--csv", required=True, help="Path to CSV with columns: name,head,sous,clean[,can_head,gender]")
    args = parser.parse_args()

    people = read_csv(args.csv)
    err = validate_totals(people)
    if err:
        print("INPUT VALIDATION ERROR:", err)
        return

    roster, status = build_roster(people)
    if roster is None:
        print("BUILD ERROR:", status)
        return

    print_roster(roster)
    summary = summarize(roster)
    print_summary(summary)

    # Cross-check against input
    desired = {p["name"]: {"H": p["H"], "S": p["S"], "C": p["C"]} for p in people}
    mismatch = []
    for name, cnt in summary.items():
        if cnt["H"] != desired[name]["H"] or cnt["S"] != desired[name]["S"] or cnt["C"] != desired[name]["C"]:
            mismatch.append((name, desired[name], dict(cnt)))
    if mismatch:
        print("\nWARNING: Mismatches detected:")
        for name, want, got in mismatch:
            print(f"  {name}: wanted {want}, got {got}")
    else:
        print("\nAll per-person totals match desired counts.")

if __name__ == "__main__":
    main()