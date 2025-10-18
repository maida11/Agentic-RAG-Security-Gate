import argparse, shutil, os

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tenant", required=True, help="U1, U2, U3, U4")
    args = ap.parse_args()
    root = os.path.join(".state", "memory", args.tenant)
    if os.path.exists(root):
        shutil.rmtree(root)
        print(f"Cleared memory for {args.tenant}")
    else:
        print(f"No memory state found for {args.tenant}")

if __name__ == "__main__":
    main()
