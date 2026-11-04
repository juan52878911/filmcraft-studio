# Grabación real de la terminal (VHS). Se ejecuta desde esta carpeta con un compose.yml en ./demo.
Output "term.mp4"
Set Shell "bash"
Set FontFamily "IosevkaTerm Nerd Font Mono"
Set FontSize 30
Set Width 1600
Set Height 900
Set Padding 56
Set Framerate 30
Set TypingSpeed 38ms
Set CursorBlink false
Set Theme { "name": "ember", "background": "#14100D", "foreground": "#EDE6DD", "cursor": "#FF5A1F", "selection": "#3A2A20", "black": "#14100D", "red": "#FF5A1F", "green": "#B8E986", "yellow": "#FFB347", "blue": "#8FD3FF", "magenta": "#E8A0BF", "cyan": "#8FD3FF", "white": "#EDE6DD", "brightBlack": "#6B5E54", "brightRed": "#FF7A45", "brightGreen": "#C9F29B", "brightYellow": "#FFC774", "brightBlue": "#B3E2FF", "brightMagenta": "#F2B8D0", "brightCyan": "#B3E2FF", "brightWhite": "#FFFFFF" }
Hide
Type "source ./rc.sh; clear"
Enter
Sleep 500ms
Show
Sleep 400ms
Type "cat compose.yml"
Enter
Sleep 900ms
Type "kling compose up -d"
Enter
Sleep 1400ms
Type "kling compose stop"
Enter
Sleep 1400ms
Type "kling compose exec cache redis-cli ping"
Enter
Sleep 1800ms
