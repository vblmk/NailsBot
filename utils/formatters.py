def format_duration_from_db(duration: str) -> str:
    return duration.replace("h", "год ").replace("m", "хв")

def format_duration_to_db(duration: str) -> str:
    return duration.replace("год ", "h").replace("хв", "m")

def is_float(element):
    try:
        float(element)
        return True
    except ValueError:
        return False