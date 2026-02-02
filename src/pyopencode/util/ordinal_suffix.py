def ordinal_suffix(n: int) -> str:
    if 10 <= n % 100 <= 13:
        return "th"
    last = n % 10
    if last == 1:
        return "st"
    elif last == 2:
        return "nd"
    elif last == 3:
        return "rd"
    else:
        return "th"

def ordinal(n: int) -> str:
    return f"{n}{ordinal_suffix(n)}"
