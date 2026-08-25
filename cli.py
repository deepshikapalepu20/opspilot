from opspilot.agent_loop import run_investigation


def main():
    goal = input("Enter investigation goal: ").strip()

    if not goal:
        print("Investigation goal cannot be empty.")
        return

    result = run_investigation(goal)

    print("\n=== INVESTIGATION RESULT ===")
    print(result)


if __name__ == "__main__":
    main()