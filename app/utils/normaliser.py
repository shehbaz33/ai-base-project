def normalize_revenue(value):
    """
    Convert human readable revenue strings like:
      - '6M'
      - '339.2B'
      - '500k'
      - '12000'
    into float values.

    Returns None if conversion fails.
    """
    if value is None:
        return None

    try:
        s = str(value).replace(",", "").strip().upper()

        if s.endswith("B"):
            return float(s[:-1]) * 1_000_000_000

        if s.endswith("M"):
            return float(s[:-1]) * 1_000_000

        if s.endswith("K"):
            return float(s[:-1]) * 1_000

        # Plain number
        return float(s)

    except Exception:
        return None
