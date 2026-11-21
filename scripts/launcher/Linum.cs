// Linum.exe for the full version (the big archive from the website).
// It starts Linum with the Python that lies next to it, without a console window,
// and on the first start puts a Linum shortcut on the Desktop and in the Start menu.
//
// Built by scripts/build_full.ps1 with the C# compiler that comes with Windows:
//   csc /target:winexe /win32icon:linum.ico /out:Linum.exe Linum.cs

using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

class Launcher
{
    [STAThread]
    static void Main()
    {
        string root = AppDomain.CurrentDomain.BaseDirectory;
        string python = Path.Combine(root, "python", "pythonw.exe");
        string main = Path.Combine(root, "main.py");
        if (!File.Exists(python) || !File.Exists(main))
        {
            MessageBox.Show("Linum files are missing. Unpack the whole archive and start Linum.exe from that folder.",
                            "Linum", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return;
        }

        // -E and -s: ignore any other Python settings on this computer
        var start = new ProcessStartInfo(python, "-E -s \"" + main + "\"");
        start.WorkingDirectory = root;
        start.UseShellExecute = false;
        Process.Start(start);

        string marker = Path.Combine(root, "data", "shortcuts-made");
        string script = Path.Combine(root, "scripts", "create_shortcut.ps1");
        if (!File.Exists(marker) && File.Exists(script))
        {
            try
            {
                var shortcuts = new ProcessStartInfo("powershell.exe",
                    "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File \"" + script + "\"");
                shortcuts.CreateNoWindow = true;
                shortcuts.UseShellExecute = false;
                Process.Start(shortcuts);
                Directory.CreateDirectory(Path.GetDirectoryName(marker));
                File.WriteAllText(marker, "");
            }
            catch (Exception)
            {
                // Without shortcuts Linum still works: it can be started with Linum.exe
            }
        }
    }
}
