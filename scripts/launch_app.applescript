set scriptPath to "/Users/paulmckay/Desktop/NHL Stats Project/scripts/launch_app.sh"

try
	do shell script "test -x " & quoted form of scriptPath
on error
	display dialog "Can't find or run the launcher script at " & scriptPath & ". Has the project been set up at this location?" with title "NHL Stats Launcher" buttons {"OK"} default button 1 with icon caution
	return
end try

try
	do shell script quoted form of scriptPath
end try
