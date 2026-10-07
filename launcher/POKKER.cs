// POKKER.exe - launcher of the packaged POKKER study tool (phase 7, spec section 3).
//
//   Double click -> one instance per Windows session (mutex Local\POKKER), checks the
//   package pieces, picks a free loopback port (47900-47919), starts
//   app\server\pokker-server.exe without a window, waits for GET /api/version, opens the
//   default browser and leaves a tray icon (Abrir POKKER / Buscar actualizaciones /
//   Abrir carpeta de datos / Cerrar POKKER).
//
//   The server shuts itself down when the browser tab stops sending heartbeats (and the
//   solver is idle); the launcher notices the child exited, removes running.json and quits.
//   "Cerrar POKKER" asks the server to stop (POST /api/app/shutdown with the launch token)
//   and kills the process tree if it is still alive after 10 s.
//
// Layout:
//   <Root>\POKKER.exe                      this launcher
//   <Root>\app\                            replaced whole by updates (Task 6)
//   %LOCALAPPDATA%\POKKER\ (or --datos=)   user data: poker.sqlite3, pokker.log, running.json...
//
// Options:
//   --diagnostico=<file>   write a JSON report (version, missing pieces, data dir, writable) and exit 0
//   --sin-navegador        do not open the browser (tests)
//   --sin-actualizar       skip the update check
//   --actualizado=<ver>    show the "POKKER se actualizo a X" balloon (passed by the updater)
//   --datos=<dir>          use another data folder (tests)
//   --actualizar-sin-preguntar, --permitir-feed-local   test options used by the updater (Task 6)
//
// Hidden test-only options (not for users; used by manual checks and Task 8):
//   --servidor=<exe>         start this executable instead of app\server\pokker-server.exe; the
//                            piece check then requires that file instead, and the server's working
//                            directory is the launcher's current directory (e.g. the backend venv's
//                            python.exe started from backend\)
//   --servidor-args=<args>   command line arguments for --servidor (e.g. "-m app.server_main")
//   --cerrar-tras=<seconds>  once the server is ready, run the tray's "Cerrar POKKER" action after
//                            that many seconds (exercises the shutdown path without a click)
//
// Security: the server only listens on 127.0.0.1; the shutdown token travels only through the
// child's environment and the X-Pokker-Token header; no registry access, no elevation.
//
// Build: launcher\build.ps1 (csc.exe of .NET Framework 4, C# 5). User-facing text is Spanish
// written with \u escapes because csc reads the source without a BOM in the system codepage.

using System;
using System.Collections;
using System.Collections.Generic;
using System.ComponentModel;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using Microsoft.Win32;

namespace Pokker
{
    static class Program
    {
        public const string Title = "POKKER";
        public const string MutexName = "Local\\POKKER";
        public const string ReleasesUrl = "https://github.com/jcolman940/POKKER_LEARNING/releases";
        public const string DefaultFeed = "https://api.github.com/repos/jcolman940/POKKER_LEARNING/releases/latest";

        static ServerProcess currentServer;
        static Paths currentPaths;

        [STAThread]
        static int Main(string[] args)
        {
            ServicePointManager.SecurityProtocol = (SecurityProtocolType)3072;   // TLS 1.2
            Options opt = Options.Parse(args);
            Paths paths = new Paths(opt.DataDir, opt.ServerExe);
            currentPaths = paths;

            if (opt.DiagnosticsFile != null)
            {
                return Diagnostics.Write(paths, opt.DiagnosticsFile);   // no UI, no mutex
            }

            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);

            bool first;
            int code;
            using (Mutex mutex = new Mutex(true, MutexName, out first))
            {
                if (!first)
                {
                    return SecondInstance.Run(paths, opt);
                }
                try
                {
                    code = RunFirst(paths, opt);
                }
                finally
                {
                    mutex.ReleaseMutex();
                }
            }
            // Released the mutex first: otherwise the replacement launcher (Task 6 update) would
            // see a running instance and only open the browser.
            if (RelaunchAfterExit != null)
            {
                try
                {
                    Process.Start(RelaunchAfterExit).Dispose();
                    Log.Write("Lanzador nuevo iniciado: " + RelaunchAfterExit.FileName + " " +
                              RelaunchAfterExit.Arguments);
                }
                catch (Exception e)
                {
                    Log.Write("No pude iniciar el lanzador nuevo: " + e.Message);
                    Ui.Error("No pude volver a abrir POKKER:\n\n" + e.Message);
                    return 1;
                }
            }
            return code;
        }

        // Set by the updater (Task 6) when this process must end and another launcher must start
        // (a new POKKER.exe, or reopening after an update from the tray). Main starts it after
        // releasing the mutex.
        public static ProcessStartInfo RelaunchAfterExit = null;

        static int RunFirst(Paths paths, Options opt)
        {
            try
            {
                Directory.CreateDirectory(paths.DataDir);
            }
            catch (Exception e)
            {
                Ui.Error("No puedo crear la carpeta de datos:\n\n" + paths.DataDir + "\n\n" + e.Message);
                return 1;
            }
            Log.Init(paths.LogFile, true);
            Log.Write("=== POKKER arranca (pid " + Process.GetCurrentProcess().Id + ", args: " +
                      string.Join(" ", opt.Raw) + ")");
            Log.Write("Carpeta de la app: " + paths.Root + " | datos: " + paths.DataDir);
            if (opt.ServerExe != null)
            {
                Log.Write("PRUEBA: servidor reemplazado por " + opt.ServerExe + " " + (opt.ServerArgs ?? "") +
                          " (cwd " + Environment.CurrentDirectory + ")");
            }
            foreach (string unknown in opt.Unknown) { Log.Write("Opci\u00f3n desconocida ignorada: " + unknown); }

            Application.SetUnhandledExceptionMode(UnhandledExceptionMode.CatchException);
            Application.ThreadException += delegate(object s, ThreadExceptionEventArgs e) { Crash(e.Exception); };
            AppDomain.CurrentDomain.UnhandledException += delegate(object s, UnhandledExceptionEventArgs e)
            {
                Log.Write("Error no controlado: " + e.ExceptionObject);
                KillServer();
            };

            Cleanup.StartBackground(paths);

            // Step 3: updates (Task 6). Must run before the server starts.
            if (opt.NoUpdate)
            {
                Log.Write("Actualizaciones: salteadas (--sin-actualizar)");
            }
            else if (Updater.CheckAtStartup(paths, opt))
            {
                Log.Write("El actualizador abri\u00f3 otra versi\u00f3n: este lanzador termina");
                return 0;
            }

            // Step 4: package pieces.
            List<string> missing = paths.MissingPieces();
            if (missing.Count > 0)
            {
                Log.Write("Faltan piezas: " + string.Join(", ", missing.ToArray()));
                string text = (missing.Count == 1 ? "Falta " + missing[0] : "Faltan " + string.Join(", ", missing.ToArray())) +
                              ": volv\u00e9 a bajar POKKER desde la p\u00e1gina de releases:\n\n" + ReleasesUrl +
                              "\n\n\u00bfQuer\u00e9s abrir esa p\u00e1gina ahora?";
                if (Ui.YesNo(text, MessageBoxIcon.Error)) { Browser.Open(ReleasesUrl); }
                return 1;
            }
            string version = paths.ReadVersion();
            Log.Write("Versi\u00f3n de la app: " + version);

            // Step 5: port.
            int port = Ports.FindFree();
            if (port < 0)
            {
                Log.Write("No hay puertos libres entre " + Ports.First + " y " + Ports.Last);
                Ui.Error("No puedo abrir POKKER: los puertos " + Ports.First + " a " + Ports.Last +
                         " de esta PC est\u00e1n ocupados.\n\nCerr\u00e1 otros programas o reinici\u00e1 la PC y prob\u00e1 de nuevo.");
                return 1;
            }
            Log.Write("Puerto elegido: " + port);

            // Steps 6-7: server.
            using (Tray tray = new Tray(paths, version))
            {
                ServerProcess server = new ServerProcess(paths, port, opt.ServerArgs);
                currentServer = server;
                tray.ShowStarting();
                string error = server.Start();
                if (error == null) { error = server.WaitReady(60000, Application.DoEvents); }
                if (error != null)
                {
                    Log.Write("El servidor no arranc\u00f3: " + error);
                    server.KillTree();
                    server.DrainOutput(2000);   // so the tail below has the server's last lines
                    Ui.Error("POKKER no pudo arrancar (" + error + ").\n\n\u00daltimas l\u00edneas del registro (" +
                             paths.LogFile + "):\n\n" + Log.Tail(20));
                    return 1;
                }

                // Step 8: running.json, browser, tray menu.
                RunningFile.Write(paths, port, server.Pid, version);
                string url = server.BaseUrl + "/";
                if (opt.NoBrowser) { Log.Write("Navegador: no se abre (--sin-navegador)"); }
                else { Browser.Open(url); }
                tray.Start(server, opt.UpdatedTo, opt.CloseAfterSeconds);
                Log.Write("POKKER listo en " + url);
                Application.Run(tray);
                RunningFile.Delete(paths);
                Log.Write("=== POKKER cerrado");
                return 0;
            }
        }

        static void KillServer()
        {
            ServerProcess s = currentServer;
            if (s != null) { try { s.KillTree(); } catch { } }
        }

        static void Crash(Exception e)
        {
            Log.Write("Error no controlado: " + e);
            KillServer();
            try { RunningFile.Delete(currentPaths); } catch { }
            Ui.Error("POKKER tuvo un error y se cierra.\n\n" + e.Message);
            Application.Exit();
        }
    }

    // ---------------------------------------------------------------- options and paths

    sealed class Options
    {
        public string DataDir;
        public string DiagnosticsFile;
        public bool NoBrowser;
        public bool NoUpdate;
        public string UpdatedTo;
        public bool UpdateWithoutAsking;   // tests (Task 6)
        public bool AllowLocalFeed;        // tests (Task 6)
        public string ServerExe;           // tests: --servidor=
        public string ServerArgs;          // tests: --servidor-args=
        public int CloseAfterSeconds;      // tests: --cerrar-tras= (0 = off)
        public string[] Raw;
        public List<string> Unknown = new List<string>();

        public static Options Parse(string[] args)
        {
            Options o = new Options();
            o.Raw = args;
            foreach (string a in args)
            {
                if (a.StartsWith("--datos=")) { o.DataDir = a.Substring(8); }
                else if (a.StartsWith("--diagnostico=")) { o.DiagnosticsFile = a.Substring(14); }
                else if (a == "--sin-navegador") { o.NoBrowser = true; }
                else if (a == "--sin-actualizar") { o.NoUpdate = true; }
                else if (a.StartsWith("--actualizado=")) { o.UpdatedTo = a.Substring(14); }
                else if (a == "--actualizar-sin-preguntar") { o.UpdateWithoutAsking = true; }
                else if (a == "--permitir-feed-local") { o.AllowLocalFeed = true; }
                else if (a.StartsWith("--servidor=")) { o.ServerExe = a.Substring(11); }
                else if (a.StartsWith("--servidor-args=")) { o.ServerArgs = a.Substring(16); }
                else if (a.StartsWith("--cerrar-tras="))
                {
                    int n;
                    if (int.TryParse(a.Substring(14), out n) && n > 0) { o.CloseAfterSeconds = n; }
                    else { o.Unknown.Add(a); }
                }
                else { o.Unknown.Add(a); }
            }
            if (string.IsNullOrEmpty(o.DataDir)) { o.DataDir = null; }
            if (string.IsNullOrEmpty(o.UpdatedTo)) { o.UpdatedTo = null; }
            o.ServerExe = string.IsNullOrEmpty(o.ServerExe) ? null : Path.GetFullPath(o.ServerExe);
            if (string.IsNullOrEmpty(o.ServerArgs)) { o.ServerArgs = null; }
            return o;
        }
    }

    sealed class Paths
    {
        public readonly string Root;      // folder of POKKER.exe
        public readonly string AppDir;    // Root\app
        public readonly string DataDir;   // %LOCALAPPDATA%\POKKER or --datos=

        public static readonly string[] Pieces =
        {
            "app\\VERSION", "app\\server\\pokker-server.exe", "app\\web\\index.html", "app\\update.json"
        };

        const string ServerPiece = "app\\server\\pokker-server.exe";

        readonly string serverOverride;   // tests: --servidor=

        public Paths(string dataDir, string serverOverride)
        {
            this.serverOverride = serverOverride;
            Root = Path.GetFullPath(AppDomain.CurrentDomain.BaseDirectory).TrimEnd('\\');
            AppDir = Path.Combine(Root, "app");
            DataDir = dataDir != null
                ? Path.GetFullPath(dataDir)
                : Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "POKKER");
        }

        public string ExePath { get { return Application.ExecutablePath; } }
        public string ServerExe
        {
            get { return serverOverride ?? Path.Combine(AppDir, "server\\pokker-server.exe"); }
        }

        public bool ServerOverridden { get { return serverOverride != null; } }
        public string WebDir { get { return Path.Combine(AppDir, "web"); } }
        public string VersionFile { get { return Path.Combine(AppDir, "VERSION"); } }
        public string UpdateJson { get { return Path.Combine(AppDir, "update.json"); } }
        public string LogFile { get { return Path.Combine(DataDir, "pokker.log"); } }
        public string RunningJson { get { return Path.Combine(DataDir, "running.json"); } }
        public string LauncherJson { get { return Path.Combine(DataDir, "launcher.json"); } }
        public string UpdatesDir { get { return Path.Combine(DataDir, "updates"); } }
        public string PreviousDataDir { get { return Path.Combine(DataDir, "datos.anterior"); } }
        public string SolverExe
        {
            get
            {
                return Path.Combine(DataDir,
                    "tools\\TexasSolver\\TexasSolver-v0.2.0-Windows\\console_solver.exe");
            }
        }

        public List<string> MissingPieces()
        {
            List<string> missing = new List<string>();
            foreach (string p in Pieces)
            {
                // With --servidor= (tests) the overriding executable replaces the server piece.
                string piece = p == ServerPiece && serverOverride != null ? serverOverride : p;
                if (!File.Exists(Path.Combine(Root, piece))) { missing.Add(piece); }
            }
            return missing;
        }

        // app\VERSION trimmed, or null when missing/unreadable.
        public string ReadVersion()
        {
            try { return File.ReadAllText(VersionFile).Trim(); }
            catch { return null; }
        }

        // Feed URL from app\update.json ({"feed": "..."}); the default feed when unreadable.
        public string ReadFeed()
        {
            try
            {
                Dictionary<string, object> d = Json.ParseObject(File.ReadAllText(UpdateJson));
                string feed = d != null ? Json.Str(d, "feed") : null;
                if (!string.IsNullOrEmpty(feed)) { return feed; }
                Log.Write("update.json sin \"feed\": uso el feed por defecto");
            }
            catch (Exception e)
            {
                Log.Write("No pude leer update.json (" + e.Message + "): uso el feed por defecto");
            }
            return Program.DefaultFeed;
        }

        // Creates and deletes a probe file in Root.
        public bool RootWritable()
        {
            string probe = Path.Combine(Root, ".pokker-escritura-" + Guid.NewGuid().ToString("N") + ".tmp");
            try
            {
                File.WriteAllText(probe, "ok");
                File.Delete(probe);
                return true;
            }
            catch
            {
                try { if (File.Exists(probe)) { File.Delete(probe); } } catch { }
                return false;
            }
        }
    }

    // ---------------------------------------------------------------- log

    static class Log
    {
        const long MaxBytes = 5L * 1024 * 1024;
        static readonly object gate = new object();
        static readonly Encoding utf8 = new UTF8Encoding(false);
        static string file;

        // rotate: pokker.log > 5 MB at startup -> pokker.1.log (only the first instance rotates).
        public static void Init(string path, bool rotate)
        {
            file = path;
            if (!rotate) { return; }
            try
            {
                FileInfo fi = new FileInfo(path);
                if (fi.Exists && fi.Length > MaxBytes)
                {
                    string old = Path.Combine(fi.DirectoryName, "pokker.1.log");
                    if (File.Exists(old)) { File.Delete(old); }
                    File.Move(path, old);
                }
            }
            catch { }
        }

        public static void Write(string message) { Append("[lanzador] " + message); }

        public static void Server(string line) { Append("[servidor] " + line); }

        static void Append(string line)
        {
            if (file == null) { return; }
            string text = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff") + " " + line + "\r\n";
            lock (gate)
            {
                try
                {
                    using (FileStream fs = new FileStream(file, FileMode.Append, FileAccess.Write,
                                                          FileShare.ReadWrite | FileShare.Delete))
                    {
                        byte[] bytes = utf8.GetBytes(text);
                        fs.Write(bytes, 0, bytes.Length);
                    }
                }
                catch { }
            }
        }

        public static string Tail(int lines)
        {
            if (file == null) { return ""; }
            lock (gate)
            {
                try
                {
                    string all;
                    using (FileStream fs = new FileStream(file, FileMode.Open, FileAccess.Read,
                                                          FileShare.ReadWrite | FileShare.Delete))
                    {
                        long start = Math.Max(0, fs.Length - 64 * 1024);
                        fs.Seek(start, SeekOrigin.Begin);
                        using (StreamReader r = new StreamReader(fs, utf8)) { all = r.ReadToEnd(); }
                    }
                    string[] parts = all.Replace("\r\n", "\n").TrimEnd('\n').Split('\n');
                    int from = Math.Max(0, parts.Length - lines);
                    string[] last = new string[parts.Length - from];
                    Array.Copy(parts, from, last, 0, last.Length);
                    return string.Join("\n", last);
                }
                catch (Exception e) { return "(no pude leer el registro: " + e.Message + ")"; }
            }
        }
    }

    // ---------------------------------------------------------------- helpers

    static class Json
    {
        public static Dictionary<string, object> ParseObject(string text)
        {
            return new JavaScriptSerializer().DeserializeObject(text) as Dictionary<string, object>;
        }

        public static string Serialize(object value)
        {
            return new JavaScriptSerializer().Serialize(value);
        }

        public static string Str(Dictionary<string, object> d, string key)
        {
            object v;
            return d.TryGetValue(key, out v) && v != null ? Convert.ToString(v) : null;
        }

        public static int Int(Dictionary<string, object> d, string key, int fallback)
        {
            object v;
            if (!d.TryGetValue(key, out v) || v == null) { return fallback; }
            try { return Convert.ToInt32(v); } catch { return fallback; }
        }

        public static bool Bool(Dictionary<string, object> d, string key)
        {
            object v;
            return d.TryGetValue(key, out v) && v is bool && (bool)v;
        }

        public static void WriteFile(string path, object value)
        {
            string tmp = path + ".tmp";
            File.WriteAllText(tmp, Serialize(value), new UTF8Encoding(false));
            if (File.Exists(path)) { File.Delete(path); }
            File.Move(tmp, path);
        }
    }

    static class Http
    {
        // Plain request to the local server (no proxy). Returns the body; status is the HTTP
        // status (0 when there was no HTTP response at all).
        public static string Send(string method, string url, int timeoutMs, string token, out int status)
        {
            status = 0;
            HttpWebRequest req = (HttpWebRequest)WebRequest.Create(url);
            req.Method = method;
            req.Proxy = null;
            req.Timeout = timeoutMs;
            req.ReadWriteTimeout = timeoutMs;
            req.KeepAlive = false;
            req.UserAgent = "POKKER-launcher";
            if (token != null) { req.Headers["X-Pokker-Token"] = token; }
            if (method == "POST") { req.ContentLength = 0; }
            HttpWebResponse resp = null;
            try
            {
                try { resp = (HttpWebResponse)req.GetResponse(); }
                catch (WebException e)
                {
                    resp = e.Response as HttpWebResponse;
                    if (resp == null) { throw; }
                }
                status = (int)resp.StatusCode;
                using (StreamReader r = new StreamReader(resp.GetResponseStream(), Encoding.UTF8))
                {
                    return r.ReadToEnd();
                }
            }
            finally
            {
                if (resp != null) { resp.Close(); }
            }
        }
    }

    static class Ui
    {
        public static void Error(string text) { Show(text, MessageBoxButtons.OK, MessageBoxIcon.Error); }

        public static void Info(string text) { Show(text, MessageBoxButtons.OK, MessageBoxIcon.Information); }

        public static bool YesNo(string text, MessageBoxIcon icon)
        {
            return Show(text, MessageBoxButtons.YesNo, icon) == DialogResult.Yes;
        }

        static DialogResult Show(string text, MessageBoxButtons buttons, MessageBoxIcon icon)
        {
            Log.Write("Cartel: " + text.Replace("\n", " "));
            // The launcher has no window: a tiny off-screen topmost owner keeps the box in front.
            using (Form owner = new Form())
            {
                owner.ShowInTaskbar = false;
                owner.FormBorderStyle = FormBorderStyle.None;
                owner.StartPosition = FormStartPosition.Manual;
                owner.Location = new Point(-32000, -32000);
                owner.Size = new Size(1, 1);
                owner.TopMost = true;
                owner.Show();
                owner.Activate();
                return MessageBox.Show(owner, text, Program.Title, buttons, icon);
            }
        }
    }

    static class Browser
    {
        public static void Open(string url)
        {
            try
            {
                Process.Start(new ProcessStartInfo(url) { UseShellExecute = true });
                Log.Write("Navegador abierto en " + url);
            }
            catch (Exception e)
            {
                Log.Write("No pude abrir el navegador: " + e.Message);
                Ui.Info("No pude abrir el navegador.\n\nAbr\u00ed esta direcci\u00f3n a mano en Edge, Chrome o Firefox:\n\n" + url);
            }
        }
    }

    static class Ports
    {
        public const int First = 47900;
        public const int Last = 47919;

        // First port in range that can be bound exclusively on 127.0.0.1 (-1 if none).
        public static int FindFree()
        {
            for (int p = First; p <= Last; p++)
            {
                if (IsFree(p)) { return p; }
            }
            return -1;
        }

        public static bool IsFree(int port)
        {
            TcpListener l = new TcpListener(IPAddress.Loopback, port);
            l.ExclusiveAddressUse = true;
            try
            {
                l.Start();
                return true;
            }
            catch (SocketException)
            {
                return false;
            }
            finally
            {
                try { l.Stop(); } catch { }
            }
        }
    }

    // ---------------------------------------------------------------- startup helpers

    static class Cleanup
    {
        // POKKER.exe.viejo and app.viejo are left behind by an update; they may stay locked for a
        // moment, so retry in the background (20 x 500 ms).
        public static void StartBackground(Paths paths)
        {
            string oldExe = paths.ExePath + ".viejo";
            string oldApp = Path.Combine(paths.Root, "app.viejo");
            if (!File.Exists(oldExe) && !Directory.Exists(oldApp)) { return; }
            Thread t = new Thread(delegate()
            {
                for (int i = 0; i < 20 && (File.Exists(oldExe) || Directory.Exists(oldApp)); i++)
                {
                    try
                    {
                        if (File.Exists(oldExe)) { File.Delete(oldExe); }
                        if (Directory.Exists(oldApp)) { Directory.Delete(oldApp, true); }
                    }
                    catch { Thread.Sleep(500); }
                }
                Log.Write(File.Exists(oldExe) || Directory.Exists(oldApp)
                    ? "No pude borrar los restos de la actualizaci\u00f3n anterior (.viejo)"
                    : "Restos de la actualizaci\u00f3n anterior borrados");
            });
            t.IsBackground = true;
            t.Start();
        }
    }

    static class RunningFile
    {
        public static void Write(Paths paths, int port, int serverPid, string version)
        {
            Dictionary<string, object> d = new Dictionary<string, object>();
            d["port"] = port;
            d["pid"] = Process.GetCurrentProcess().Id;
            d["server_pid"] = serverPid;
            d["version"] = version;
            try { Json.WriteFile(paths.RunningJson, d); }
            catch (Exception e) { Log.Write("No pude escribir running.json: " + e.Message); }
        }

        // {port, pid} of the running instance, or null when missing/invalid.
        public static Dictionary<string, object> Read(Paths paths)
        {
            try
            {
                if (!File.Exists(paths.RunningJson)) { return null; }
                Dictionary<string, object> d = Json.ParseObject(File.ReadAllText(paths.RunningJson));
                if (d == null || Json.Int(d, "port", 0) <= 0 || Json.Int(d, "pid", 0) <= 0) { return null; }
                return d;
            }
            catch { return null; }
        }

        public static void Delete(Paths paths)
        {
            try { if (File.Exists(paths.RunningJson)) { File.Delete(paths.RunningJson); } }
            catch (Exception e) { Log.Write("No pude borrar running.json: " + e.Message); }
        }
    }

    static class SecondInstance
    {
        // Another POKKER owns the mutex: open the browser on it and exit 0. While the first one is
        // still starting (no running.json yet) wait up to 15 s.
        public static int Run(Paths paths, Options opt)
        {
            Log.Init(paths.LogFile, false);
            DateTime deadline = DateTime.UtcNow.AddSeconds(15);
            while (true)
            {
                Dictionary<string, object> info = RunningFile.Read(paths);
                if (info != null && LauncherAlive(Json.Int(info, "pid", 0)))
                {
                    string url = "http://127.0.0.1:" + Json.Int(info, "port", 0) + "/";
                    Log.Write("Ya hay un POKKER abierto (pid " + Json.Int(info, "pid", 0) + "): " +
                              (opt.NoBrowser ? "no abro el navegador (--sin-navegador)" : "abro " + url));
                    if (!opt.NoBrowser) { Browser.Open(url); }
                    return 0;
                }
                if (DateTime.UtcNow > deadline) { break; }
                Thread.Sleep(500);
            }
            Log.Write("Ya hay un POKKER abri\u00e9ndose o cerr\u00e1ndose (sin running.json v\u00e1lido)");
            if (!opt.NoBrowser)
            {
                Ui.Info("POKKER ya se est\u00e1 abriendo o cerrando. Esper\u00e1 unos segundos y prob\u00e1 de nuevo.");
            }
            return 0;
        }

        static bool LauncherAlive(int pid)
        {
            try
            {
                using (Process p = Process.GetProcessById(pid))
                {
                    if (p.HasExited) { return false; }
                    string me = Process.GetCurrentProcess().ProcessName;
                    return string.Equals(p.ProcessName, me, StringComparison.OrdinalIgnoreCase);
                }
            }
            catch { return false; }
        }
    }

    static class Diagnostics
    {
        // --diagnostico=<file>: JSON report, no UI. Exit 0 (2 if the report cannot be written).
        public static int Write(Paths paths, string file)
        {
            List<string> missing = paths.MissingPieces();
            List<string> found = new List<string>();
            foreach (string p in Paths.Pieces) { if (!missing.Contains(p)) { found.Add(p); } }
            Dictionary<string, object> d = new Dictionary<string, object>();
            d["version"] = paths.ReadVersion();
            d["root"] = paths.Root;
            d["encontradas"] = found;
            d["faltantes"] = missing;
            d["data_dir"] = paths.DataDir;
            d["app_escribible"] = paths.RootWritable();
            d["solver"] = File.Exists(paths.SolverExe);
            try
            {
                File.WriteAllText(Path.GetFullPath(file), Json.Serialize(d), new UTF8Encoding(false));
                return 0;
            }
            catch
            {
                return 2;
            }
        }
    }

    // ---------------------------------------------------------------- updates (Task 6 hook)

    static class Updater
    {
        // Step 3 of the startup (spec 4). Returns true when this process must exit; to start a
        // replacement launcher set Program.RelaunchAfterExit (started after the mutex is released).
        // Task 6 implements it; for now it is a no-op that only logs.
        public static bool CheckAtStartup(Paths paths, Options opt)
        {
            Log.Write("Actualizaciones: todav\u00eda no implementadas (feed " + paths.ReadFeed() + ")");
            return false;
        }

        // "Buscar actualizaciones" from the tray menu (Task 6). The menu item stays disabled while
        // this is false.
        public static bool TrayCheckAvailable { get { return false; } }

        public static void CheckFromTray(Tray tray) { }
    }

    // ---------------------------------------------------------------- server process

    sealed class ServerStatus
    {
        public bool SolverBusy;
        public int SolverPending;
        public int Work { get { return SolverPending + (SolverBusy ? 1 : 0); } }
    }

    sealed class ServerProcess
    {
        readonly Paths paths;
        readonly int port;
        readonly string token;
        readonly string arguments;   // tests: --servidor-args=
        Process process;
        JobObject job;

        public event EventHandler Exited;

        public ServerProcess(Paths paths, int port, string arguments)
        {
            this.paths = paths;
            this.port = port;
            this.arguments = arguments;
            this.token = NewToken();
        }

        public string BaseUrl { get { return "http://127.0.0.1:" + port; } }
        public int Pid { get { return process != null ? process.Id : 0; } }

        public bool HasExited
        {
            get
            {
                try { return process == null || process.HasExited; }
                catch { return true; }
            }
        }

        static string NewToken()
        {
            byte[] bytes = new byte[32];
            using (RNGCryptoServiceProvider rng = new RNGCryptoServiceProvider()) { rng.GetBytes(bytes); }
            StringBuilder sb = new StringBuilder(64);
            foreach (byte b in bytes) { sb.Append(b.ToString("x2")); }
            return sb.ToString();
        }

        // Starts the server; null on success, otherwise a short Spanish reason.
        public string Start()
        {
            ProcessStartInfo psi = new ProcessStartInfo(paths.ServerExe);
            if (arguments != null) { psi.Arguments = arguments; }
            psi.UseShellExecute = false;
            psi.CreateNoWindow = true;
            psi.RedirectStandardOutput = true;
            psi.RedirectStandardError = true;
            psi.StandardOutputEncoding = Encoding.UTF8;
            psi.StandardErrorEncoding = Encoding.UTF8;
            // With --servidor= (tests) keep the caller's directory (e.g. backend\ for "-m app...").
            psi.WorkingDirectory = paths.ServerOverridden
                ? Environment.CurrentDirectory
                : Path.GetDirectoryName(paths.ServerExe);

            // The packaged server only sees what the launcher decides: drop inherited POKER_*.
            List<string> inherited = new List<string>();
            foreach (DictionaryEntry e in psi.EnvironmentVariables)
            {
                string k = (string)e.Key;
                if (k.StartsWith("POKER_", StringComparison.OrdinalIgnoreCase)) { inherited.Add(k); }
            }
            foreach (string k in inherited) { psi.EnvironmentVariables.Remove(k); }

            psi.EnvironmentVariables["POKER_DATA_DIR"] = paths.DataDir;
            psi.EnvironmentVariables["POKER_RESOURCES_DIR"] = paths.AppDir;
            psi.EnvironmentVariables["POKER_WEB_DIR"] = paths.WebDir;
            psi.EnvironmentVariables["POKER_HOST"] = "127.0.0.1";
            psi.EnvironmentVariables["POKER_PORT"] = port.ToString();
            psi.EnvironmentVariables["POKER_LAUNCH_TOKEN"] = token;
            psi.EnvironmentVariables["POKER_UPDATE_FEED_URL"] = paths.ReadFeed();
            if (File.Exists(paths.SolverExe))
            {
                psi.EnvironmentVariables["POKER_SOLVER_PATH"] = paths.SolverExe;
                Log.Write("TexasSolver encontrado: " + paths.SolverExe);
            }
            psi.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
            psi.EnvironmentVariables["PYTHONUNBUFFERED"] = "1";

            Process p = new Process();
            p.StartInfo = psi;
            p.EnableRaisingEvents = true;
            p.OutputDataReceived += delegate(object s, DataReceivedEventArgs e) { if (e.Data != null) { Log.Server(e.Data); } };
            p.ErrorDataReceived += delegate(object s, DataReceivedEventArgs e) { if (e.Data != null) { Log.Server(e.Data); } };
            p.Exited += OnExited;
            try
            {
                p.Start();
            }
            catch (Exception e)
            {
                Log.Write("No pude lanzar " + paths.ServerExe + ": " + e.Message);
                p.Dispose();
                return "no se pudo lanzar el servidor: " + e.Message;
            }
            process = p;
            Log.Write("Servidor lanzado (pid " + p.Id + ") en " + BaseUrl);
            try
            {
                job = new JobObject();
                job.Assign(p);
            }
            catch (Exception e)
            {
                Log.Write("Aviso: no pude atar el servidor al lanzador (job object): " + e.Message);
            }
            p.BeginOutputReadLine();
            p.BeginErrorReadLine();
            return null;
        }

        void OnExited(object sender, EventArgs e)
        {
            int code = -1;
            try { code = process.ExitCode; } catch { }
            Log.Write("El servidor termin\u00f3 (c\u00f3digo " + code + ")");
            EventHandler h = Exited;
            if (h != null) { h(this, EventArgs.Empty); }
        }

        // Polls GET /api/version every 500 ms (2 s timeout per try) until it answers or timeoutMs
        // passes. pump keeps the UI alive (balloon). null on success, otherwise the reason.
        public string WaitReady(int timeoutMs, Action pump)
        {
            Stopwatch sw = Stopwatch.StartNew();
            while (sw.ElapsedMilliseconds < timeoutMs)
            {
                if (HasExited) { return "el servidor se cerr\u00f3 al arrancar"; }
                try
                {
                    int status;
                    string body = Http.Send("GET", BaseUrl + "/api/version", 2000, null, out status);
                    if (status == 200)
                    {
                        Dictionary<string, object> d = Json.ParseObject(body);
                        if (d != null && d.ContainsKey("app"))
                        {
                            Log.Write("Servidor listo en " + sw.ElapsedMilliseconds + " ms: " + body.Trim());
                            return null;
                        }
                    }
                    Log.Write("Respuesta inesperada de /api/version (" + status + ")");
                }
                catch (Exception) { }
                Stopwatch pause = Stopwatch.StartNew();
                while (pause.ElapsedMilliseconds < 500)
                {
                    if (pump != null) { pump(); }
                    Thread.Sleep(50);
                }
            }
            return "el servidor no respondi\u00f3 en " + (timeoutMs / 1000) + " segundos";
        }

        // GET /api/app/status, or null when the server does not answer.
        public ServerStatus GetStatus()
        {
            try
            {
                int status;
                string body = Http.Send("GET", BaseUrl + "/api/app/status", 2000, null, out status);
                if (status != 200) { return null; }
                Dictionary<string, object> d = Json.ParseObject(body);
                if (d == null) { return null; }
                ServerStatus s = new ServerStatus();
                s.SolverBusy = Json.Bool(d, "solver_busy");
                s.SolverPending = Json.Int(d, "solver_pending", 0);
                return s;
            }
            catch { return null; }
        }

        // POST /api/app/shutdown with the token, wait waitMs, then kill the tree if still alive.
        public void Shutdown(int waitMs)
        {
            if (HasExited) { return; }
            try
            {
                int status;
                Http.Send("POST", BaseUrl + "/api/app/shutdown", 3000, token, out status);
                Log.Write("Pedido de apagado enviado (HTTP " + status + ")");
            }
            catch (Exception e)
            {
                Log.Write("No pude pedir el apagado: " + e.Message);
            }
            bool exited = false;
            try { exited = process.WaitForExit(waitMs); } catch { exited = true; }
            if (!exited)
            {
                Log.Write("El servidor sigue vivo tras " + (waitMs / 1000) + " s: lo termino");
                KillTree();
            }
        }

        // Waits (at most ms) until the redirected stdout/stderr reached EOF and were logged.
        public void DrainOutput(int ms)
        {
            Process p = process;
            if (p == null) { return; }
            Thread t = new Thread(delegate() { try { p.WaitForExit(); } catch { } });
            t.IsBackground = true;
            t.Start();
            t.Join(ms);
        }

        public void KillTree()
        {
            if (process == null) { return; }
            try
            {
                if (process.HasExited) { return; }
                ProcessStartInfo psi = new ProcessStartInfo("taskkill.exe", "/T /F /PID " + process.Id);
                psi.UseShellExecute = false;
                psi.CreateNoWindow = true;
                using (Process k = Process.Start(psi)) { k.WaitForExit(10000); }
                if (!process.WaitForExit(5000)) { process.Kill(); }
                Log.Write("\u00c1rbol del servidor terminado (taskkill)");
            }
            catch (Exception e)
            {
                Log.Write("No pude terminar el servidor: " + e.Message);
            }
        }
    }

    // Kill-on-close job: if the launcher dies abruptly, Windows kills the server (and the solver
    // it started) too. Purely a safety net; the normal path is the shutdown request.
    sealed class JobObject
    {
        const int JobObjectExtendedLimitInformation = 9;
        const uint JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000;

        [StructLayout(LayoutKind.Sequential)]
        struct BasicLimit
        {
            public long PerProcessUserTimeLimit;
            public long PerJobUserTimeLimit;
            public uint LimitFlags;
            public UIntPtr MinimumWorkingSetSize;
            public UIntPtr MaximumWorkingSetSize;
            public uint ActiveProcessLimit;
            public UIntPtr Affinity;
            public uint PriorityClass;
            public uint SchedulingClass;
        }

        [StructLayout(LayoutKind.Sequential)]
        struct IoCounters
        {
            public ulong ReadOperationCount, WriteOperationCount, OtherOperationCount;
            public ulong ReadTransferCount, WriteTransferCount, OtherTransferCount;
        }

        [StructLayout(LayoutKind.Sequential)]
        struct ExtendedLimit
        {
            public BasicLimit Basic;
            public IoCounters Io;
            public UIntPtr ProcessMemoryLimit;
            public UIntPtr JobMemoryLimit;
            public UIntPtr PeakProcessMemoryUsed;
            public UIntPtr PeakJobMemoryUsed;
        }

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        static extern IntPtr CreateJobObject(IntPtr attributes, string name);

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool SetInformationJobObject(IntPtr job, int infoClass, ref ExtendedLimit info, uint length);

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);

        readonly IntPtr handle;   // intentionally never closed: closing it kills the server

        public JobObject()
        {
            handle = CreateJobObject(IntPtr.Zero, null);
            if (handle == IntPtr.Zero) { throw new Win32Exception(); }
            ExtendedLimit info = new ExtendedLimit();
            info.Basic.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
            if (!SetInformationJobObject(handle, JobObjectExtendedLimitInformation, ref info,
                                         (uint)Marshal.SizeOf(typeof(ExtendedLimit))))
            {
                throw new Win32Exception();
            }
        }

        public void Assign(Process p)
        {
            if (!AssignProcessToJobObject(handle, p.Handle)) { throw new Win32Exception(); }
        }
    }

    // ---------------------------------------------------------------- tray

    sealed class Tray : ApplicationContext
    {
        const int StatusEveryMs = 15000;

        readonly Paths paths;
        readonly string version;
        readonly NotifyIcon icon;
        readonly Control invoker;   // marshals background callbacks to the UI thread
        ServerProcess server;
        System.Threading.Timer statusTimer;
        System.Windows.Forms.Timer closeTimer;   // tests: --cerrar-tras=
        int polling;
        volatile bool finished;
        volatile bool closing;
        ToolStripMenuItem updateItem;
        ToolStripMenuItem closeItem;

        public Tray(Paths paths, string version)
        {
            this.paths = paths;
            this.version = version;
            invoker = new Control();
            IntPtr forceHandle = invoker.Handle;
            icon = new NotifyIcon();
            icon.Icon = LoadIcon();
            icon.Text = Program.Title + " \u00b7 abriendo\u2026";
            icon.Visible = true;
        }

        // build.ps1 embeds pokker.ico (/resource) so the tray gets the real 16 px frame instead of
        // the 32 px exe icon scaled down.
        static Icon LoadIcon()
        {
            try
            {
                using (Stream s = typeof(Tray).Assembly.GetManifestResourceStream("pokker.ico"))
                {
                    if (s != null) { return new Icon(s, SystemInformation.SmallIconSize); }
                }
            }
            catch { }
            try { return Icon.ExtractAssociatedIcon(Application.ExecutablePath); }
            catch { return SystemIcons.Application; }
        }

        public void ShowStarting()
        {
            icon.ShowBalloonTip(5000, Program.Title, "Abriendo POKKER\u2026", ToolTipIcon.Info);
        }

        public void Start(ServerProcess server, string updatedTo, int closeAfterSeconds)
        {
            this.server = server;
            ContextMenuStrip menu = new ContextMenuStrip();
            ToolStripMenuItem open = new ToolStripMenuItem("Abrir POKKER", null, delegate { OpenApp(); });
            open.Font = new Font(open.Font, FontStyle.Bold);
            menu.Items.Add(open);
            updateItem = new ToolStripMenuItem("Buscar actualizaciones", null, delegate { Updater.CheckFromTray(this); });
            updateItem.Enabled = Updater.TrayCheckAvailable;
            menu.Items.Add(updateItem);
            menu.Items.Add(new ToolStripMenuItem("Abrir carpeta de datos", null, delegate { OpenDataFolder(); }));
            menu.Items.Add(new ToolStripSeparator());
            closeItem = new ToolStripMenuItem("Cerrar POKKER", null, delegate { CloseRequested(); });
            menu.Items.Add(closeItem);
            icon.ContextMenuStrip = menu;
            icon.DoubleClick += delegate { OpenApp(); };
            icon.Text = Program.Title;

            // While closing on purpose (menu, Task 6 update) the StopServer continuation finishes.
            server.Exited += delegate { RunOnUi(OnServerExited); };
            if (server.HasExited) { RunOnUi(OnServerExited); }

            statusTimer = new System.Threading.Timer(delegate { PollStatus(); }, null, 3000, StatusEveryMs);
            SystemEvents.SessionEnding += OnSessionEnding;

            if (updatedTo != null)
            {
                icon.ShowBalloonTip(8000, Program.Title, "POKKER se actualiz\u00f3 a " + updatedTo + ".", ToolTipIcon.Info);
            }

            if (closeAfterSeconds > 0)
            {
                // Test-only (--cerrar-tras=): the same action as the "Cerrar POKKER" menu item.
                closeTimer = new System.Windows.Forms.Timer();
                closeTimer.Interval = closeAfterSeconds * 1000;
                closeTimer.Tick += delegate
                {
                    closeTimer.Stop();
                    Log.Write("PRUEBA: --cerrar-tras=" + closeAfterSeconds + " -> Cerrar POKKER");
                    CloseRequested();
                };
                closeTimer.Start();
            }
        }

        public ServerProcess Server { get { return server; } }
        public Paths Paths { get { return paths; } }
        public string Version { get { return version; } }

        public void RunOnUi(Action action)
        {
            try
            {
                if (!invoker.IsDisposed) { invoker.BeginInvoke(action); }
            }
            catch (InvalidOperationException) { }
        }

        void OpenApp()
        {
            if (server != null) { Browser.Open(server.BaseUrl + "/"); }
        }

        void OpenDataFolder()
        {
            try { Process.Start("explorer.exe", "\"" + paths.DataDir + "\""); }
            catch (Exception e) { Log.Write("No pude abrir la carpeta de datos: " + e.Message); }
        }

        void PollStatus()
        {
            if (Interlocked.Exchange(ref polling, 1) == 1) { return; }
            try
            {
                if (closing || server == null || server.HasExited) { return; }
                ServerStatus s = server.GetStatus();
                if (s == null) { return; }
                string text = s.Work > 0
                    ? Program.Title + " \u00b7 resolviendo " + s.Work + (s.Work == 1 ? " spot" : " spots")
                    : Program.Title;
                RunOnUi(delegate { if (!finished && !closing) { icon.Text = text; } });
            }
            finally
            {
                Interlocked.Exchange(ref polling, 0);
            }
        }

        // "Cerrar POKKER": confirm if the solver works, then ask the server to stop (10 s, then
        // taskkill), then finish the tray.
        public void CloseRequested()
        {
            if (closing || finished) { return; }
            ServerStatus s = server.GetStatus();
            if (s != null && s.Work > 0)
            {
                string text = "Hay " + s.Work + (s.Work == 1 ? " spot" : " spots") +
                              " en cola; se retoman la pr\u00f3xima vez.\n\n\u00bfCerrar POKKER igual?";
                if (!Ui.YesNo(text, MessageBoxIcon.Question)) { return; }
            }
            StopServer("Cerrar POKKER", delegate { Finish("cerrado por el usuario"); });
        }

        // Stops the server in the background and then runs 'then' on the UI thread. Used by the
        // close item and (Task 6) by the tray update before applying it.
        public void StopServer(string reason, Action then)
        {
            closing = true;
            Log.Write("Apagando el servidor: " + reason);
            icon.Text = Program.Title + " \u00b7 cerrando\u2026";
            if (closeItem != null) { closeItem.Enabled = false; }
            if (updateItem != null) { updateItem.Enabled = false; }
            Thread t = new Thread(delegate()
            {
                server.Shutdown(10000);
                RunOnUi(then);
            });
            t.IsBackground = true;
            t.Start();
        }

        void OnServerExited()
        {
            if (!closing) { Finish("el servidor se cerr\u00f3 solo (latido o error)"); }
        }

        void Finish(string reason)
        {
            if (finished) { return; }
            finished = true;
            Log.Write("Cerrando el lanzador: " + reason);
            RunningFile.Delete(paths);
            icon.Visible = false;
            ExitThread();
        }

        void OnSessionEnding(object sender, SessionEndingEventArgs e)
        {
            Log.Write("Windows cierra la sesi\u00f3n: apago el servidor");
            closing = true;
            if (server != null) { server.Shutdown(5000); }
            RunOnUi(delegate { Finish("fin de la sesi\u00f3n de Windows"); });
        }

        protected override void Dispose(bool disposing)
        {
            if (disposing)
            {
                SystemEvents.SessionEnding -= OnSessionEnding;
                if (statusTimer != null) { statusTimer.Dispose(); }
                if (closeTimer != null) { closeTimer.Dispose(); }
                icon.Visible = false;
                icon.Dispose();
                invoker.Dispose();
            }
            base.Dispose(disposing);
        }
    }
}
