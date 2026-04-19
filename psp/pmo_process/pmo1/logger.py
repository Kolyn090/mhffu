import re

class LogStyle:
    DIGIT_COLOR = "\033[96m"

    # Reset
    RESET = "\033[0m"

    # Standard colors
    BLACK   = "\033[30m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN    = "\033[36m"
    WHITE   = "\033[37m"

    # Bright colors
    BRIGHT_BLACK   = "\033[90m"
    BRIGHT_RED     = "\033[91m"
    BRIGHT_GREEN   = "\033[92m"
    BRIGHT_YELLOW  = "\033[93m"
    BRIGHT_BLUE    = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN    = "\033[96m"
    BRIGHT_WHITE   = "\033[97m"

    # Background colors
    BG_RED     = "\033[41m"
    BG_GREEN   = "\033[42m"
    BG_YELLOW  = "\033[43m"
    BG_BLUE    = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN    = "\033[46m"
    BG_WHITE   = "\033[47m"

    # Styles
    BOLD      = "\033[1m"
    DIM       = "\033[2m"
    UNDERLINE = "\033[4m"

class Logger:
    log_file = None
    enable = True

    COLORS = {
        "[INFO]": LogStyle.BRIGHT_BLUE,
        "[WARN]": LogStyle.BRIGHT_YELLOW,
        "[ERROR]": LogStyle.BRIGHT_RED,
        "[DEBUG]": LogStyle.BRIGHT_BLACK,
    }

    @staticmethod
    def _color_digits(text: str) -> str:
        return re.sub(r'\d', lambda m: f"{LogStyle.DIGIT_COLOR}{m.group()}{LogStyle.RESET}", text)

    @staticmethod
    def _log(type: str, message: str, indent: int = 0, override_color: str = None, end='\n'):
        if not Logger.enable:
            return

        prefix = "  " * indent
        color = override_color if override_color else Logger.COLORS.get(type, "")

        if override_color:
            # Full line override (no digit coloring)
            print(f"{prefix}{color}{type} {message}{LogStyle.RESET}", end=end)
        else:
            colored_message = Logger._color_digits(message)
            print(f"{prefix}{color}{type}{LogStyle.RESET} {colored_message}", end=end)
        # ===== File output (no colors) =====
        if Logger.log_file:
            if type:
                file_line = f"{prefix}{type} {message}"
            else:
                file_line = f"{prefix}{message}"

            Logger.log_file.write(file_line + end)
            Logger.log_file.flush()

    @staticmethod
    def info(message: str, indent: int = 0, end='\n'):
        Logger._log("[INFO]", message, indent, end=end)

    @staticmethod
    def warn(message: str, indent: int = 0, end='\n'):
        Logger._log("[WARN]", message, indent, end=end)

    @staticmethod
    def error(message: str, indent: int = 0, end='\n'):
        Logger._log("[ERROR]", message, indent, end=end)

    @staticmethod
    def debug(message: str, indent: int = 0, end='\n'):
        Logger._log("[DEBUG]", message, indent, end=end)

    @staticmethod
    def highlight(message: str, indent: int = 0, color=LogStyle.YELLOW, end='\n'):
        Logger._log("[INFO]", message, indent, override_color=color, end=end)

    @staticmethod
    def empty(message: str, indent: int = 0, end='\n'):
        Logger._log("", message, indent, end=end)

    @staticmethod
    def newline(end='\n'):
        Logger._log("", "", 0, end=end)

    @staticmethod
    def set_log_file(filepath: str, mode='w'):
        Logger.log_file = open(filepath, mode, encoding='utf-8')

    @staticmethod
    def close():
        if Logger.log_file:
            Logger.log_file.close()
            Logger.log_file = None
