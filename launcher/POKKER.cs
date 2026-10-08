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
//   --actualizar-sin-preguntar  (tests) apply an available update without the window; update
//                          messages (read-only folder, failure) are only logged, never shown
//   --permitir-feed-local  (tests) also accept http://127.0.0.1:<port> for the feed and the
//                          downloads; without it only the GitHub hosts are accepted
//
// Updates (spec 4): app\update.json "feed" -> GitHub releases/latest JSON; POKKER-X.Y.Z.zip and
// .zip.sha256 are downloaded to <data>\updates, verified, unpacked into app.nuevo, the database
// is copied to <data>\datos.anterior, then app -> app.viejo, new app -> app (and, when it differs,
// the new launcher is copied to POKKER.exe.nuevo, then POKKER.exe -> POKKER.exe.viejo and
// POKKER.exe.nuevo -> POKKER.exe). Any failure undoes every step (Rollback).
// "Saltear esta version" is remembered in <data>\launcher.json {"skipped": "X.Y.Z"}.
//
// Hidden test-only options (not for users; used by manual checks and Task 8):
//   --respuesta=<r>          answer the update window without showing it: actualizar | ahora-no |
//                            saltear | cancelar (= actualizar, then press Cancelar during the
//                            download)
//   --servidor=<exe>         (only together with --datos=; ignored and logged otherwise)
//                            start this executable instead of app\server\pokker-server.exe; the
//                            piece check then requires that file instead, and the server's working
//                            directory is the launcher's current directory (e.g. the backend venv's
//                            python.exe started from backend\)
//   --servidor-args=<args>   command line arguments for --servidor (e.g. "-m app.server_main")
//   --buscar-tras=<seconds>  once the server is ready, run the tray's "Buscar actualizaciones"
//                            after that many seconds (with --respuesta= it needs no click)
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
            Opt = opt;
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

        // Options of this run (the tray's update check reads them).
        public static Options Opt;

        // Arguments to start POKKER.exe again: this run's arguments minus the update-related
        // ones, plus 'extra'. The working directory is kept (the --servidor test flag needs it).
        public static ProcessStartInfo Relaunch(string exe, Options opt, params string[] extra)
        {
            List<string> args = new List<string>();
            foreach (string a in opt.Raw)
            {
                if (a == "--sin-actualizar" || a == "--actualizar-sin-preguntar" || a.StartsWith("--actualizado=") ||
                    a.StartsWith("--respuesta=") || a.StartsWith("--buscar-tras=") ||
                    a.StartsWith("--diagnostico=")) { continue; }
                args.Add(QuoteArg(a));
            }
            foreach (string a in extra) { args.Add(QuoteArg(a)); }
            ProcessStartInfo psi = new ProcessStartInfo(exe, string.Join(" ", args.ToArray()));
            psi.UseShellExecute = false;
            psi.WorkingDirectory = Environment.CurrentDirectory;
            return psi;
        }

        // Windows command-line quoting (CommandLineToArgvW rules).
        static string QuoteArg(string a)
        {
            if (a.Length > 0 && a.IndexOfAny(new char[] { ' ', '\t', '"' }) < 0) { return a; }
            StringBuilder sb = new StringBuilder("\"");
            int slashes = 0;
            foreach (char c in a)
            {
                if (c == '\\') { slashes++; continue; }
                if (c == '"') { sb.Append('\\', slashes * 2 + 1); }
                else { sb.Append('\\', slashes); }
                slashes = 0;
                sb.Append(c);
            }
            sb.Append('\\', slashes * 2);
            sb.Append('"');
            return sb.ToString();
        }

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
            if (opt.ServerIgnored)
            {
                Log.Write("PRUEBA: --servidor= ignorado: solo vale junto con --datos=");
            }
            if (opt.TestAnswer != null)
            {
                Log.Write("PRUEBA: respuesta a la actualizaci\u00f3n fijada: " + opt.TestAnswer);
            }
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
                try { RunningFile.Delete(currentPaths); } catch { }
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
                // 60 s is plenty for a normal start; a server that is still alive after that is
                // usually migrating a big database (decision backfill): keep waiting up to 10 min.
                if (error == null) { error = server.WaitReady(60000, 600000, Application.DoEvents, tray.ShowMigrating); }
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
                tray.Start(server, opt.UpdatedTo, opt.CloseAfterSeconds, opt.CheckAfterSeconds);
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
        public int CheckAfterSeconds;      // tests: --buscar-tras= (0 = off)
        public bool ServerIgnored;         // --servidor= given without --datos= (ignored)
        public string TestAnswer;          // tests: --respuesta= (actualizar|ahora-no|saltear|cancelar)
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
                else if (a.StartsWith("--buscar-tras="))
                {
                    int n;
                    if (int.TryParse(a.Substring(14), out n) && n > 0) { o.CheckAfterSeconds = n; }
                    else { o.Unknown.Add(a); }
                }
                else if (a.StartsWith("--respuesta="))
                {
                    string r = a.Substring(12);
                    if (r == "actualizar" || r == "ahora-no" || r == "saltear" || r == "cancelar") { o.TestAnswer = r; }
                    else { o.Unknown.Add(a); }
                }
                else { o.Unknown.Add(a); }
            }
            if (string.IsNullOrEmpty(o.DataDir)) { o.DataDir = null; }
            if (string.IsNullOrEmpty(o.UpdatedTo)) { o.UpdatedTo = null; }
            o.ServerExe = string.IsNullOrEmpty(o.ServerExe) ? null : Path.GetFullPath(o.ServerExe);
            if (o.ServerExe != null && o.DataDir == null)
            {
                // Test-only flag: never run a foreign server against the user's real data.
                o.ServerExe = null;
                o.ServerArgs = null;
                o.ServerIgnored = true;
            }
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

        // The pieces this run needs: with --servidor= (tests) the overriding executable replaces
        // the server piece. Relative to Root, or absolute for the override.
        public List<string> EffectivePieces()
        {
            List<string> pieces = new List<string>();
            foreach (string p in Pieces)
            {
                pieces.Add(p == ServerPiece && serverOverride != null ? serverOverride : p);
            }
            return pieces;
        }

        public List<string> MissingPieces()
        {
            List<string> missing = new List<string>();
            foreach (string piece in EffectivePieces())
            {
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
            if (File.Exists(path)) { File.Replace(tmp, path, null); }   // atomic swap
            else { File.Move(tmp, path); }
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

        // A message that unattended runs (--actualizar-sin-preguntar, tests) only log.
        public static void Notice(bool quiet, string text, MessageBoxIcon icon)
        {
            if (quiet) { Log.Write("Aviso (sin cartel): " + FirstLine(text)); }
            else { Show(text, MessageBoxButtons.OK, icon); }
        }

        public static string FirstLine(string text)
        {
            string t = text.Trim();
            int nl = t.IndexOf('\n');
            return nl < 0 ? t : t.Substring(0, nl).TrimEnd('\r');
        }

        static DialogResult Show(string text, MessageBoxButtons buttons, MessageBoxIcon icon)
        {
            Log.Write("Cartel: " + FirstLine(text));
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
            string staleNewExe = paths.ExePath + ".nuevo";   // an update died before its renames
            if (File.Exists(staleNewExe))
            {
                try
                {
                    File.Delete(staleNewExe);
                    Log.Write("Borr\u00e9 un POKKER.exe.nuevo que qued\u00f3 de una actualizaci\u00f3n interrumpida");
                }
                catch (Exception e) { Log.Write("No pude borrar POKKER.exe.nuevo: " + e.Message); }
            }
            if (!Directory.Exists(paths.AppDir) && Directory.Exists(oldApp))
            {
                // An update died between "app -> app.viejo" and "new app -> app": app.viejo is the
                // only complete version, so bring it back instead of deleting it.
                try
                {
                    Fs.Move(oldApp, paths.AppDir, true);
                    Log.Write("No hab\u00eda carpeta app: restaur\u00e9 app.viejo como app");
                }
                catch (Exception e)
                {
                    Log.Write("No hay carpeta app y no pude restaurar app.viejo: " + e.Message);
                    oldApp = null;   // never delete the only copy
                }
            }
            if (oldApp != null && !Directory.Exists(oldApp)) { oldApp = null; }
            if (!File.Exists(oldExe) && oldApp == null) { return; }
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
            worker = t;
            t.Start();
        }

        static Thread worker;

        // The updater renames app -> app.viejo: it must not race this cleanup (ruling R4).
        public static void Wait(int ms)
        {
            Thread t = worker;
            if (t != null && !t.Join(ms)) { Log.Write("La limpieza de .viejo sigue en curso tras " + (ms / 1000) + " s"); }
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
            foreach (string p in paths.EffectivePieces()) { if (!missing.Contains(p)) { found.Add(p); } }
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

    // ---------------------------------------------------------------- updates (spec 4)

    enum UpdateChoice { Update, Later, Skip }

    enum ApplyResult { Applied, AppliedNewExe, Cancelled, Failed }

    sealed class UpdateException : Exception
    {
        public UpdateException(string message) : base(message) { }
    }

    sealed class Release
    {
        public string Tag;
        public string Version;     // "X.Y.Z" (tag without "v" and suffixes)
        public string Body;
        public string HtmlUrl;
        public string ZipName;     // POKKER-X.Y.Z.zip
        public string ZipUrl;
        public long ZipSize;
        public string ShaUrl;

        // "Ver todas las versiones": the releases page of the repo.
        public string AllReleasesUrl
        {
            get
            {
                // Only a GitHub page is opened; anything else from the feed falls back to ours.
                if (HtmlUrl == null || !HtmlUrl.StartsWith("https://github.com/", StringComparison.OrdinalIgnoreCase))
                {
                    return Program.ReleasesUrl;
                }
                int i = HtmlUrl.IndexOf("/releases/", StringComparison.OrdinalIgnoreCase);
                return i > 0 ? HtmlUrl.Substring(0, i) + "/releases" : Program.ReleasesUrl;
            }
        }
    }

    static class Versions
    {
        // "v1.2.3" / "1.2.3-rc1" -> {1,2,3}; null when it is not X.Y.Z.
        public static int[] Parse(string text)
        {
            if (text == null) { return null; }
            string t = text.Trim();
            if (t.StartsWith("v") || t.StartsWith("V")) { t = t.Substring(1); }
            int cut = t.IndexOfAny(new char[] { '-', '+', ' ' });
            if (cut >= 0) { t = t.Substring(0, cut); }
            string[] parts = t.Split('.');
            if (parts.Length != 3) { return null; }
            int[] n = new int[3];
            for (int i = 0; i < 3; i++)
            {
                if (!int.TryParse(parts[i], System.Globalization.NumberStyles.None,
                                  System.Globalization.CultureInfo.InvariantCulture, out n[i])) { return null; }
            }
            return n;
        }

        public static int Compare(int[] a, int[] b)
        {
            for (int i = 0; i < 3; i++) { if (a[i] != b[i]) { return a[i].CompareTo(b[i]); } }
            return 0;
        }

        public static string Format(int[] v) { return v[0] + "." + v[1] + "." + v[2]; }
    }

    // Which URLs the updater may contact (spec 4.3 + constraints): the GitHub API feed; release
    // downloads of the feed's repo (https://github.com/<owner>/<repo>/releases/download/...) and
    // GitHub's redirect hosts. http://127.0.0.1 only with --permitir-feed-local (tests).
    sealed class UrlPolicy
    {
        // GitHub's download hosts; github.com itself is only accepted under the repo's
        // /releases/download/ path (first hop or redirect).
        static readonly string[] RedirectHosts =
        {
            "objects.githubusercontent.com", "release-assets.githubusercontent.com"
        };

        readonly bool allowLocal;
        readonly string downloadPrefix;   // "/owner/repo/releases/download/" (lowercase)

        public UrlPolicy(string feed, bool allowLocal)
        {
            this.allowLocal = allowLocal;
            string owner = "jcolman940", repo = "POKKER_LEARNING";
            Uri u;
            if (Uri.TryCreate(feed, UriKind.Absolute, out u) && u.Host == "api.github.com")
            {
                string[] seg = u.AbsolutePath.Trim('/').Split('/');
                if (seg.Length >= 3 && seg[0] == "repos") { owner = seg[1]; repo = seg[2]; }
            }
            downloadPrefix = ("/" + owner + "/" + repo + "/releases/download/").ToLowerInvariant();
        }

        public bool IsLocal(string url)
        {
            Uri u;
            return Uri.TryCreate(url, UriKind.Absolute, out u) && IsLocal(u);
        }

        bool IsLocal(Uri u)
        {
            return allowLocal && u.Scheme == Uri.UriSchemeHttp && u.Host == "127.0.0.1";
        }

        // null when the URL may be used, otherwise the reason.
        public string CheckFeed(string url)
        {
            Uri u;
            if (!Uri.TryCreate(url, UriKind.Absolute, out u)) { return "direcci\u00f3n inv\u00e1lida: " + url; }
            if (IsLocal(u)) { return null; }
            if (u.Scheme == Uri.UriSchemeHttps && u.Host == "api.github.com") { return null; }
            return "host no permitido para el feed: " + u.Scheme + "://" + u.Authority;
        }

        // firstHop: the asset URL from the feed; later hops are redirects.
        public string CheckDownload(string url, bool firstHop)
        {
            Uri u;
            if (!Uri.TryCreate(url, UriKind.Absolute, out u)) { return "direcci\u00f3n inv\u00e1lida: " + url; }
            if (IsLocal(u)) { return null; }
            if (u.Scheme != Uri.UriSchemeHttps) { return "solo se acepta https: " + url; }
            if (u.Host == "github.com" && u.AbsolutePath.ToLowerInvariant().StartsWith(downloadPrefix)) { return null; }
            if (firstHop) { return "no es una descarga de las releases de POKKER: " + url; }
            if (Array.IndexOf(RedirectHosts, u.Host) >= 0) { return null; }
            return "redirecci\u00f3n a un host no permitido: " + u.Host;
        }
    }

    // HTTP for the updater: redirects are followed by hand so every hop is checked before it is
    // contacted (and ResponseUri is checked again).
    static class Net
    {
        // timeoutMs: connect/response; readTimeoutMs: each read of the body.
        public static HttpWebResponse Open(string url, UrlPolicy policy, bool feed, string userAgent, int timeoutMs,
                                           int readTimeoutMs)
        {
            for (int hop = 0; hop < 6; hop++)
            {
                string why = feed ? (hop == 0 ? policy.CheckFeed(url) : "el feed redirige a " + url)
                                  : policy.CheckDownload(url, hop == 0);
                if (why != null) { throw new UpdateException(why); }
                HttpWebRequest req = (HttpWebRequest)WebRequest.Create(url);
                req.AllowAutoRedirect = false;
                req.UserAgent = userAgent;
                req.Accept = feed ? "application/vnd.github+json" : "application/octet-stream";
                req.Timeout = timeoutMs;
                req.ReadWriteTimeout = readTimeoutMs;
                if (policy.IsLocal(url)) { req.Proxy = null; }
                HttpWebResponse resp;
                try { resp = (HttpWebResponse)req.GetResponse(); }
                catch (WebException e)
                {
                    resp = e.Response as HttpWebResponse;
                    if (resp == null) { throw new UpdateException("sin conexi\u00f3n (" + e.Message + ")"); }
                }
                int code = (int)resp.StatusCode;
                if (code == 301 || code == 302 || code == 303 || code == 307 || code == 308)
                {
                    string location = resp.Headers["Location"];
                    resp.Close();
                    if (string.IsNullOrEmpty(location)) { throw new UpdateException("redirecci\u00f3n sin destino"); }
                    url = new Uri(new Uri(url), location).AbsoluteUri;
                    continue;
                }
                if (code != 200)
                {
                    resp.Close();
                    throw new UpdateException("HTTP " + code + " en " + url);
                }
                string after = feed ? policy.CheckFeed(resp.ResponseUri.AbsoluteUri)
                                    : policy.CheckDownload(resp.ResponseUri.AbsoluteUri, hop == 0);
                if (after != null) { resp.Close(); throw new UpdateException(after); }
                return resp;
            }
            throw new UpdateException("demasiadas redirecciones");
        }

        public static string ReadString(string url, UrlPolicy policy, bool feed, string userAgent, int timeoutMs, int maxBytes)
        {
            using (HttpWebResponse resp = Open(url, policy, feed, userAgent, timeoutMs, timeoutMs))
            using (Stream s = resp.GetResponseStream())
            using (MemoryStream ms = new MemoryStream())
            {
                byte[] buf = new byte[16384];
                int n;
                while ((n = s.Read(buf, 0, buf.Length)) > 0)
                {
                    ms.Write(buf, 0, n);
                    if (ms.Length > maxBytes) { throw new UpdateException("respuesta demasiado grande"); }
                }
                return Encoding.UTF8.GetString(ms.ToArray());
            }
        }

        // progress(done, total); total is -1 when unknown. cancel() is polled between chunks.
        public static void ToFile(string url, UrlPolicy policy, string userAgent, string path,
                                  Action<long, long> progress, Func<bool> cancel)
        {
            using (HttpWebResponse resp = Open(url, policy, false, userAgent, 15000, 30000))
            using (Stream s = resp.GetResponseStream())
            using (FileStream fs = new FileStream(path, FileMode.Create, FileAccess.Write, FileShare.None))
            {
                long total = resp.ContentLength;
                long done = 0;
                byte[] buf = new byte[81920];
                int n;
                while ((n = s.Read(buf, 0, buf.Length)) > 0)
                {
                    if (cancel()) { throw new OperationCanceledException(); }
                    fs.Write(buf, 0, n);
                    done += n;
                    progress(done, total);
                }
                if (total >= 0 && done != total)
                {
                    throw new UpdateException("descarga incompleta (" + done + " de " + total + " bytes)");
                }
            }
        }
    }

    // Steps done by an update, undone in reverse order on failure or cancel.
    sealed class Rollback
    {
        readonly List<KeyValuePair<string, Action>> steps = new List<KeyValuePair<string, Action>>();

        public void Add(string what, Action undo) { steps.Add(new KeyValuePair<string, Action>(what, undo)); }

        public void Clear() { steps.Clear(); }

        public void Undo()
        {
            for (int i = steps.Count - 1; i >= 0; i--)
            {
                try
                {
                    steps[i].Value();
                    Log.Write("Vuelta atr\u00e1s: " + steps[i].Key);
                }
                catch (Exception e)
                {
                    Log.Write("Vuelta atr\u00e1s FALL\u00d3 (" + steps[i].Key + "): " + e.Message);
                }
            }
            steps.Clear();
        }
    }

    static class Fs
    {
        // Directory/file renames can fail for a moment (antivirus, indexer): retry 10 x 300 ms.
        public static void Move(string from, string to, bool directory)
        {
            for (int i = 0; ; i++)
            {
                try
                {
                    if (directory) { Directory.Move(from, to); } else { File.Move(from, to); }
                    return;
                }
                catch (IOException) { if (i >= 9) { throw; } }
                catch (UnauthorizedAccessException) { if (i >= 9) { throw; } }
                Thread.Sleep(300);
            }
        }

        public static void DeleteDir(string dir)
        {
            for (int i = 0; Directory.Exists(dir); i++)
            {
                try { Directory.Delete(dir, true); }
                catch (Exception) { if (i >= 9) { throw; } Thread.Sleep(300); }
            }
        }

        public static void DeleteFile(string file)
        {
            try { if (File.Exists(file)) { File.Delete(file); } } catch { }
        }

        public static string Sha256(string file)
        {
            using (SHA256 sha = SHA256.Create())
            using (FileStream fs = new FileStream(file, FileMode.Open, FileAccess.Read, FileShare.Read))
            {
                StringBuilder sb = new StringBuilder(64);
                foreach (byte b in sha.ComputeHash(fs)) { sb.Append(b.ToString("X2")); }
                return sb.ToString();
            }
        }

        public static string Megabytes(long bytes)
        {
            return (bytes / 1048576.0).ToString("0.0") + " MB";
        }
    }

    static class Updater
    {
        const int FeedTimeoutMs = 8000;

        static string UserAgent(string current) { return "POKKER/" + (current ?? "0.0.0"); }

        // GET <feed>. Returns the newer release, or null with the reason (upToDate tells "no news"
        // apart from offline / invalid answers).
        public static Release Query(Paths paths, Options opt, string current, out string reason, out bool upToDate)
        {
            reason = null;
            upToDate = false;
            int[] cur = Versions.Parse(current);
            if (cur == null) { reason = "versi\u00f3n actual inv\u00e1lida (" + current + ")"; return null; }
            string feed = paths.ReadFeed();
            UrlPolicy policy = new UrlPolicy(feed, opt.AllowLocalFeed);
            Dictionary<string, object> d;
            try
            {
                d = Json.ParseObject(Net.ReadString(feed, policy, true, UserAgent(current), FeedTimeoutMs, 4 * 1024 * 1024));
            }
            catch (Exception e)
            {
                reason = "no pude consultar " + feed + ": " + e.Message;
                return null;
            }
            if (d == null) { reason = "respuesta inv\u00e1lida del feed"; return null; }
            string tag = Json.Str(d, "tag_name");
            int[] next = Versions.Parse(tag);
            if (next == null) { reason = "tag_name inv\u00e1lido en el feed: " + tag; return null; }
            if (Versions.Compare(next, cur) <= 0)
            {
                upToDate = true;
                reason = "sin novedades (\u00faltima " + tag + ", tengo " + current + ")";
                return null;
            }
            Release r = new Release();
            r.Tag = tag;
            r.Version = Versions.Format(next);
            r.Body = Json.Str(d, "body") ?? "";
            r.HtmlUrl = Json.Str(d, "html_url");
            r.ZipName = "POKKER-" + r.Version + ".zip";
            object assetsObj;
            object[] assets = d.TryGetValue("assets", out assetsObj) ? assetsObj as object[] : null;
            if (assets != null)
            {
                foreach (object o in assets)
                {
                    Dictionary<string, object> a = o as Dictionary<string, object>;
                    if (a == null) { continue; }
                    string name = Json.Str(a, "name");
                    string url = Json.Str(a, "browser_download_url");
                    if (name == r.ZipName)
                    {
                        r.ZipUrl = url;
                        object size;
                        if (a.TryGetValue("size", out size) && size != null)
                        {
                            try { r.ZipSize = Convert.ToInt64(size); } catch { }
                        }
                    }
                    else if (name == r.ZipName + ".sha256") { r.ShaUrl = url; }
                }
            }
            if (r.ZipUrl == null || r.ShaUrl == null)
            {
                reason = "la release " + tag + " no trae " + r.ZipName + " y " + r.ZipName + ".sha256";
                return null;
            }
            return r;
        }

        // Step 3 of the startup. Returns true when this process must exit (a new POKKER.exe was
        // installed: Program.RelaunchAfterExit starts it once the mutex is released).
        public static bool CheckAtStartup(Paths paths, Options opt)
        {
            string current = paths.ReadVersion();
            if (current == null) { Log.Write("Actualizaciones: no hay app\\VERSION, no busco"); return false; }
            string reason;
            bool upToDate;
            Release r = Query(paths, opt, current, out reason, out upToDate);
            if (r == null) { Log.Write("Actualizaciones: " + reason); return false; }
            Log.Write("Actualizaciones: hay una versi\u00f3n nueva " + r.Version + " (tengo " + current + ")");

            UpdateChoice choice;
            if (opt.UpdateWithoutAsking)
            {
                Log.Write("Actualizaciones: se aplica sin preguntar (--actualizar-sin-preguntar)");
                choice = UpdateChoice.Update;
            }
            else if (r.Version == ReadSkipped(paths))
            {
                Log.Write("Actualizaciones: la versi\u00f3n " + r.Version + " fue salteada por el usuario");
                return false;
            }
            else
            {
                choice = Ask(r, current, opt);
            }
            if (!Accept(paths, r, choice)) { return false; }

            ApplyResult res = Apply(paths, opt, r, current);
            if (res == ApplyResult.Applied)
            {
                opt.UpdatedTo = r.Version;
                return false;
            }
            if (res == ApplyResult.AppliedNewExe)
            {
                Program.RelaunchAfterExit = Program.Relaunch(paths.ExePath, opt, "--sin-actualizar", "--actualizado=" + r.Version);
                return true;
            }
            return false;   // cancelled or failed: continue with the current version
        }

        // "Buscar actualizaciones" from the tray: query in the background, then ask; on yes stop
        // the server, apply and reopen POKKER (the new or the current launcher).
        public static bool TrayCheckAvailable { get { return true; } }

        public static void CheckFromTray(Tray tray)
        {
            Options opt = Program.Opt;
            Paths paths = tray.Paths;
            string current = paths.ReadVersion();
            tray.SetUpdateItemEnabled(false);
            Log.Write("Buscar actualizaciones (\u00edcono)");
            Thread t = new Thread(delegate()
            {
                string reason;
                bool upToDate;
                Release r = Query(paths, opt, current, out reason, out upToDate);
                tray.RunOnUi(delegate { TrayAnswer(tray, opt, current, r, reason, upToDate); });
            });
            t.IsBackground = true;
            t.Start();
        }

        static void TrayAnswer(Tray tray, Options opt, string current, Release r, string reason, bool upToDate)
        {
            if (tray.IsClosing) { return; }
            tray.SetUpdateItemEnabled(true);
            Paths paths = tray.Paths;
            if (r == null)
            {
                Log.Write("Actualizaciones: " + reason);
                bool quiet = Unattended(opt);
                if (upToDate) { Ui.Notice(quiet, "Ya ten\u00e9s la \u00faltima versi\u00f3n de POKKER (" + current + ").", MessageBoxIcon.Information); }
                else { Ui.Notice(quiet, "No pude consultar si hay una versi\u00f3n nueva de POKKER. Prob\u00e1 m\u00e1s tarde.\n\n(" + reason + ")", MessageBoxIcon.Information); }
                return;
            }
            Log.Write("Actualizaciones: hay una versi\u00f3n nueva " + r.Version + " (tengo " + current + ")");
            if (!Accept(paths, r, Ask(r, current, opt))) { return; }
            // Before stopping the server: a read-only folder must not cost the user a restart.
            if (!CheckWritable(paths, opt, current)) { return; }
            ServerStatus s = tray.Server.GetStatus();
            if (s != null && s.Work > 0)
            {
                string text = "Hay " + s.Work + (s.Work == 1 ? " spot" : " spots") +
                              " en cola; se retoman la pr\u00f3xima vez.\n\n\u00bfActualizar igual?";
                if (Unattended(opt)) { Log.Write("Solver ocupado (" + s.Work + "): actualizo igual (prueba)"); }
                else if (!Ui.YesNo(text, MessageBoxIcon.Question)) { return; }
            }
            tray.StopServer("actualizar a " + r.Version, delegate
            {
                ApplyResult res = Apply(paths, opt, r, current);
                bool ok = res == ApplyResult.Applied || res == ApplyResult.AppliedNewExe;
                Program.RelaunchAfterExit = ok
                    ? Program.Relaunch(paths.ExePath, opt, "--sin-actualizar", "--actualizado=" + r.Version)
                    : Program.Relaunch(paths.ExePath, opt, "--sin-actualizar");
                tray.Finish(ok ? "reabrir con la versi\u00f3n " + r.Version : "reabrir con la versi\u00f3n " + current);
            });
        }

        // Test runs never show a window that waits for a click.
        static bool Unattended(Options opt) { return opt.UpdateWithoutAsking || opt.TestAnswer != null; }

        static UpdateChoice Ask(Release r, string current, Options opt)
        {
            if (opt.UpdateWithoutAsking) { return UpdateChoice.Update; }
            if (opt.TestAnswer != null)
            {
                Log.Write("PRUEBA: respuesta al cartel de actualizaci\u00f3n: " + opt.TestAnswer);
                if (opt.TestAnswer == "ahora-no") { return UpdateChoice.Later; }
                if (opt.TestAnswer == "saltear") { return UpdateChoice.Skip; }
                return UpdateChoice.Update;   // actualizar, cancelar (cancels the download later)
            }
            return UpdateDialog.Ask(r, current);
        }

        static bool Accept(Paths paths, Release r, UpdateChoice choice)
        {
            if (choice == UpdateChoice.Update) { return true; }
            if (choice == UpdateChoice.Skip)
            {
                SaveSkipped(paths, r.Version);
                Log.Write("Actualizaciones: el usuario saltea la versi\u00f3n " + r.Version);
            }
            else
            {
                Log.Write("Actualizaciones: el usuario eligi\u00f3 \"Ahora no\"");
            }
            return false;
        }

        static string ReadSkipped(Paths paths)
        {
            try
            {
                if (!File.Exists(paths.LauncherJson)) { return null; }
                Dictionary<string, object> d = Json.ParseObject(File.ReadAllText(paths.LauncherJson));
                return d != null ? Json.Str(d, "skipped") : null;
            }
            catch { return null; }
        }

        static void SaveSkipped(Paths paths, string version)
        {
            Dictionary<string, object> d = null;
            try
            {
                if (File.Exists(paths.LauncherJson)) { d = Json.ParseObject(File.ReadAllText(paths.LauncherJson)); }
            }
            catch { }
            if (d == null) { d = new Dictionary<string, object>(); }
            d["skipped"] = version;
            try { Json.WriteFile(paths.LauncherJson, d); }
            catch (Exception e) { Log.Write("No pude escribir launcher.json: " + e.Message); }
        }

        // Probe file in Root; when it fails, says so (only logged when unattended) and returns false.
        static bool CheckWritable(Paths paths, Options opt, string current)
        {
            if (paths.RootWritable()) { return true; }
            Log.Write("No puedo actualizar: la carpeta " + paths.Root + " no es escribible");
            bool quiet = Unattended(opt);
            Ui.Notice(quiet, "No puedo actualizar en esta carpeta: mov\u00e9 POKKER a Documentos (u otra carpeta tuya).\n\n" +
                      paths.Root + "\n\nSigo con la versi\u00f3n " + current + ".", MessageBoxIcon.Warning);
            return false;
        }

        // Spec 4.3. The server must not be running. Messages are only logged when unattended.
        public static ApplyResult Apply(Paths paths, Options opt, Release r, string current)
        {
            if (!CheckWritable(paths, opt, current)) { return ApplyResult.Failed; }
            bool quiet = Unattended(opt);
            UpdateJob job = new UpdateJob(paths, opt, r, current);
            ProgressDialog.Run("Actualizando POKKER a " + r.Version, job.Run);
            if (job.Result == ApplyResult.Failed)
            {
                Ui.Notice(quiet, "No pude actualizar POKKER: " + job.Error + "\n\nSigo con la versi\u00f3n " + current + ".",
                          MessageBoxIcon.Error);
            }
            return job.Result;
        }
    }

    // The update itself (spec 4.3 steps 1-6), run on the progress dialog's worker thread.
    sealed class UpdateJob
    {
        readonly Paths paths;
        readonly Options opt;
        readonly Release release;
        readonly string current;

        public ApplyResult Result = ApplyResult.Failed;
        public string Error;

        public UpdateJob(Paths paths, Options opt, Release release, string current)
        {
            this.paths = paths;
            this.opt = opt;
            this.release = release;
            this.current = current;
        }

        string NewDir { get { return Path.Combine(paths.Root, "app.nuevo"); } }
        string OldDir { get { return Path.Combine(paths.Root, "app.viejo"); } }
        string OldExe { get { return paths.ExePath + ".viejo"; } }
        string NewExe { get { return paths.ExePath + ".nuevo"; } }

        public void Run(ProgressDialog ui)
        {
            Rollback rb = new Rollback();
            string zip = Path.Combine(paths.UpdatesDir, release.ZipName);
            UrlPolicy policy = new UrlPolicy(paths.ReadFeed(), opt.AllowLocalFeed);
            string ua = "POKKER/" + current;
            Log.Write("Actualizaci\u00f3n " + current + " -> " + release.Version + ": empieza");
            try
            {
                // Leftovers of an earlier update: the background cleanup first (ruling R4), then
                // synchronously, so the renames below never meet an existing target.
                ui.SetStage("Preparando\u2026");
                Cleanup.Wait(15000);
                try
                {
                    Fs.DeleteDir(OldDir);
                    Fs.DeleteDir(NewDir);
                    if (File.Exists(OldExe)) { File.Delete(OldExe); }
                    if (File.Exists(NewExe)) { File.Delete(NewExe); }
                }
                catch (Exception e)
                {
                    throw new UpdateException("no pude borrar los restos de una actualizaci\u00f3n anterior (" + e.Message + ")");
                }

                // 1. Download (+ .sha256) and verify.
                Directory.CreateDirectory(paths.UpdatesDir);
                string shaText = Net.ReadString(release.ShaUrl, policy, false, ua, 15000, 4096);
                string expected = ParseSha256(shaText);
                if (expected == null)
                {
                    Log.Write("Contenido del .sha256 rechazado: " + shaText.Substring(0, Math.Min(shaText.Length, 100)).Trim());
                    throw new UpdateException("El archivo de verificaci\u00f3n de la actualizaci\u00f3n no es v\u00e1lido");
                }
                ui.SetStage("Descargando POKKER " + release.Version + "\u2026");
                bool cancelForTest = opt.TestAnswer == "cancelar";
                Net.ToFile(release.ZipUrl, policy, ua, zip,
                    delegate(long done, long total)
                    {
                        ui.SetProgress(done, total > 0 ? total : release.ZipSize);
                        if (cancelForTest && done > 0) { cancelForTest = false; Log.Write("PRUEBA: cancelo la descarga"); ui.Cancel(); }
                    },
                    delegate { return ui.Cancelled; });
                Log.Write("Descargado " + release.ZipName + " (" + new FileInfo(zip).Length + " bytes)");
                ui.SetStage("Verificando la descarga\u2026");
                string actual = Fs.Sha256(zip);
                if (actual != expected)
                {
                    throw new UpdateException("la descarga est\u00e1 da\u00f1ada (SHA-256 " + actual + ", se esperaba " + expected + ")");
                }
                Log.Write("SHA-256 verificado: " + actual);
                CheckCancel(ui);

                // 2. Unpack into app.nuevo and validate it.
                ui.SetStage("Descomprimiendo\u2026");
                rb.Add("borrar app.nuevo", delegate { Fs.DeleteDir(NewDir); });
                SafeExtract(zip, NewDir);
                string pkg = PackageRoot(NewDir);
                foreach (string piece in Paths.Pieces)
                {
                    if (!File.Exists(Path.Combine(pkg, piece)))
                    {
                        throw new UpdateException("el paquete nuevo no trae " + piece);
                    }
                }
                string newVersion = File.ReadAllText(Path.Combine(pkg, "app\\VERSION")).Trim();
                if (newVersion != release.Version)
                {
                    throw new UpdateException("el paquete dice ser la versi\u00f3n " + newVersion + " y no " + release.Version);
                }
                // From here on the swap is quick and must not be interrupted. LockCancel is atomic
                // with the Cancelar click, so a click that raced in is still honoured here.
                if (!ui.LockCancel()) { throw new OperationCanceledException(); }

                // 3. Copy of the database (the server is not running).
                ui.SetStage("Guardando una copia de tus datos\u2026");
                BackupDatabase();

                // 4. app -> app.viejo, new app -> app.
                ui.SetStage("Instalando\u2026");
                Fs.Move(paths.AppDir, OldDir, true);
                rb.Add("app.viejo -> app", delegate { Fs.Move(OldDir, paths.AppDir, true); });
                string newApp = Path.Combine(pkg, "app");
                Fs.Move(newApp, paths.AppDir, true);
                rb.Add("app -> app.nuevo", delegate { Fs.Move(paths.AppDir, newApp, true); });
                Log.Write("Carpeta app reemplazada (la anterior qued\u00f3 en app.viejo)");

                // 5. New POKKER.exe when it differs.
                bool newExe = false;
                string zipExe = Path.Combine(pkg, "POKKER.exe");
                if (!File.Exists(zipExe))
                {
                    Log.Write("AVISO: el paquete de la actualizaci\u00f3n no trae POKKER.exe: sigo con el lanzador actual");
                }
                else if (Fs.Sha256(zipExe) == Fs.Sha256(paths.ExePath))
                {
                    Log.Write("POKKER.exe no cambi\u00f3");
                }
                else
                {
                    // Copy first (the slow part, may fail) next to it, then two renames: POKKER.exe
                    // is never missing for longer than a rename.
                    rb.Add("borrar POKKER.exe.nuevo", delegate { Fs.DeleteFile(NewExe); });
                    File.Copy(zipExe, NewExe, true);
                    Fs.Move(paths.ExePath, OldExe, false);
                    rb.Add("POKKER.exe.viejo -> POKKER.exe", delegate { Fs.Move(OldExe, paths.ExePath, false); });
                    Fs.Move(NewExe, paths.ExePath, false);
                    rb.Add("POKKER.exe -> POKKER.exe.nuevo", delegate { Fs.Move(paths.ExePath, NewExe, false); });
                    newExe = true;
                    Log.Write("POKKER.exe nuevo copiado (el anterior qued\u00f3 como POKKER.exe.viejo)");
                }

                // Done: nothing to undo any more.
                rb.Clear();
                try { Fs.DeleteDir(NewDir); } catch (Exception e) { Log.Write("No pude borrar app.nuevo: " + e.Message); }
                if (!newExe) { Cleanup.StartBackground(paths); }   // app.viejo; a new launcher does it itself
                Result = newExe ? ApplyResult.AppliedNewExe : ApplyResult.Applied;
                Log.Write("Actualizaci\u00f3n aplicada: " + current + " -> " + release.Version);
            }
            catch (OperationCanceledException)
            {
                Log.Write("Actualizaci\u00f3n cancelada por el usuario: vuelta atr\u00e1s");
                rb.Undo();
                Result = ApplyResult.Cancelled;
            }
            catch (Exception e)
            {
                Error = e is UpdateException || e is IOException || e is UnauthorizedAccessException
                    ? e.Message : e.GetType().Name + ": " + e.Message;
                Log.Write("Actualizaci\u00f3n fallida: " + Error + ": vuelta atr\u00e1s");
                if (!(e is UpdateException)) { Log.Write(e.ToString()); }
                rb.Undo();
                Result = ApplyResult.Failed;
            }
            finally
            {
                Fs.DeleteFile(zip);
                if (Result != ApplyResult.Applied && Result != ApplyResult.AppliedNewExe)
                {
                    try { Fs.DeleteDir(NewDir); } catch (Exception e) { Log.Write("No pude borrar app.nuevo: " + e.Message); }
                }
            }
        }

        // First token of a .sha256 file ("HASH" or "HASH  name"), BOM and whitespace ignored;
        // uppercase, or null unless it is exactly 64 hex digits.
        public static string ParseSha256(string text)
        {
            if (text == null) { return null; }
            string t = text.Replace("\ufeff", "").Trim();
            string[] tokens = t.Split(new char[] { ' ', '\t', '\r', '\n', '*' }, StringSplitOptions.RemoveEmptyEntries);
            if (tokens.Length == 0 || tokens[0].Length != 64) { return null; }
            foreach (char c in tokens[0])
            {
                bool hex = (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F');
                if (!hex) { return null; }
            }
            return tokens[0].ToUpperInvariant();
        }

        // Extracts entry by entry, refusing the whole zip when any entry's destination is outside
        // dir (zip-slip), instead of relying on ExtractToDirectory's own check.
        static void SafeExtract(string zip, string dir)
        {
            string root = Path.GetFullPath(dir).TrimEnd('\\') + "\\";
            using (System.IO.Compression.ZipArchive archive = System.IO.Compression.ZipFile.OpenRead(zip))
            {
                foreach (System.IO.Compression.ZipArchiveEntry entry in archive.Entries)
                {
                    if (!EntryPath(root, entry).StartsWith(root, StringComparison.OrdinalIgnoreCase))
                    {
                        throw new UpdateException("el paquete trae una ruta no permitida: " + entry.FullName);
                    }
                }
                Directory.CreateDirectory(root);
                foreach (System.IO.Compression.ZipArchiveEntry entry in archive.Entries)
                {
                    string dest = EntryPath(root, entry);
                    if (entry.FullName.EndsWith("/") || entry.FullName.EndsWith("\\"))
                    {
                        Directory.CreateDirectory(dest);
                        continue;
                    }
                    Directory.CreateDirectory(Path.GetDirectoryName(dest));
                    System.IO.Compression.ZipFileExtensions.ExtractToFile(entry, dest, false);
                }
            }
        }

        static string EntryPath(string root, System.IO.Compression.ZipArchiveEntry entry)
        {
            try { return Path.GetFullPath(Path.Combine(root, entry.FullName.Replace('/', '\\'))); }
            catch (Exception) { throw new UpdateException("el paquete trae una ruta no v\u00e1lida: " + entry.FullName); }
        }

        static void CheckCancel(ProgressDialog ui)
        {
            if (ui.Cancelled) { throw new OperationCanceledException(); }
        }

        // The zip holds either POKKER\{POKKER.exe, app\} or {POKKER.exe, app\} at its root.
        static string PackageRoot(string dir)
        {
            if (Directory.Exists(Path.Combine(dir, "app"))) { return dir; }
            string[] subs = Directory.GetDirectories(dir);
            if (subs.Length == 1 && Directory.Exists(Path.Combine(subs[0], "app"))) { return subs[0]; }
            throw new UpdateException("el paquete nuevo no trae la carpeta app");
        }

        // poker.sqlite3 (+ -wal/-shm) -> datos.anterior\ (replacing the previous copy).
        void BackupDatabase()
        {
            string db = Path.Combine(paths.DataDir, "poker.sqlite3");
            if (!File.Exists(db)) { Log.Write("No hay base de datos todav\u00eda: no hago copia"); return; }
            // Copy into a fresh temp folder, then swap it in: datos.anterior is either the previous
            // complete copy or the new complete copy, never a mix.
            string dest = paths.PreviousDataDir;
            string tmp = dest + ".tmp";
            string old = dest + ".old";
            Fs.DeleteDir(tmp);
            Fs.DeleteDir(old);
            Directory.CreateDirectory(tmp);
            foreach (string suffix in new string[] { "", "-wal", "-shm" })
            {
                string src = db + suffix;
                if (File.Exists(src)) { File.Copy(src, Path.Combine(tmp, "poker.sqlite3" + suffix), false); }
            }
            if (Directory.Exists(dest)) { Fs.Move(dest, old, true); }
            try
            {
                Fs.Move(tmp, dest, true);
            }
            catch
            {
                if (Directory.Exists(old) && !Directory.Exists(dest)) { Fs.Move(old, dest, true); }
                throw;
            }
            try { Fs.DeleteDir(old); } catch (Exception e) { Log.Write("No pude borrar " + old + ": " + e.Message); }
            Log.Write("Copia de la base en " + dest);
        }
    }

    // ---------------------------------------------------------------- update windows

    // Spec 4.2: the "new version" window (news, download size, link, three buttons).
    sealed class UpdateDialog : Form
    {
        UpdateChoice choice = UpdateChoice.Later;

        UpdateDialog(Release r, string current)
        {
            Text = "Actualizaci\u00f3n de POKKER";
            FormBorderStyle = FormBorderStyle.FixedDialog;
            MaximizeBox = false;
            MinimizeBox = false;
            StartPosition = FormStartPosition.CenterScreen;
            TopMost = true;
            ClientSize = new Size(520, 400);
            Font = SystemFonts.MessageBoxFont;
            try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch { }

            Label title = new Label();
            title.Text = "Hay una versi\u00f3n nueva de POKKER: " + r.Version + " (ten\u00e9s " + current + ")";
            title.Font = new Font(Font.FontFamily, Font.Size + 2, FontStyle.Bold);
            title.SetBounds(16, 14, 488, 28);
            Controls.Add(title);

            Label news = new Label();
            news.Text = "Novedades:";
            news.SetBounds(16, 48, 488, 20);
            Controls.Add(news);

            TextBox body = new TextBox();
            body.Multiline = true;
            body.ReadOnly = true;
            body.ScrollBars = ScrollBars.Vertical;
            body.Text = (r.Body.Length > 0 ? r.Body : "(sin descripci\u00f3n)").Replace("\r\n", "\n").Replace("\n", "\r\n");
            body.SetBounds(16, 70, 488, 220);
            body.TabStop = false;
            Controls.Add(body);

            Label size = new Label();
            size.Text = "Tama\u00f1o de la descarga: " + (r.ZipSize > 0 ? Fs.Megabytes(r.ZipSize) : "desconocido");
            size.SetBounds(16, 298, 300, 20);
            Controls.Add(size);

            LinkLabel all = new LinkLabel();
            all.Text = "Ver todas las versiones";
            all.TextAlign = ContentAlignment.MiddleRight;
            all.SetBounds(320, 298, 184, 20);
            string releasesUrl = r.AllReleasesUrl;
            all.LinkClicked += delegate { Browser.Open(releasesUrl); };
            Controls.Add(all);

            Button update = MakeButton("Actualizar ahora", UpdateChoice.Update, 16);
            Button later = MakeButton("Ahora no", UpdateChoice.Later, 186);
            MakeButton("Saltear esta versi\u00f3n", UpdateChoice.Skip, 356);
            AcceptButton = update;
            CancelButton = later;
        }

        Button MakeButton(string text, UpdateChoice value, int x)
        {
            Button b = new Button();
            b.Text = text;
            b.SetBounds(x, 344, 148, 34);
            b.Click += delegate { choice = value; Close(); };
            Controls.Add(b);
            return b;
        }

        public static UpdateChoice Ask(Release r, string current)
        {
            using (UpdateDialog d = new UpdateDialog(r, current))
            {
                d.ShowDialog();
                Log.Write("Cartel de actualizaci\u00f3n: " + d.choice);
                return d.choice;
            }
        }
    }

    // Progress of an update: stage, bar, bytes and Cancelar. The work runs on a worker thread;
    // every UI call from it is marshalled.
    sealed class ProgressDialog : Form
    {
        readonly Label stage = new Label();
        readonly ProgressBar bar = new ProgressBar();
        readonly Label bytes = new Label();
        readonly Button cancel = new Button();
        volatile bool cancelled;
        volatile bool done;

        ProgressDialog(string title)
        {
            Text = title;
            FormBorderStyle = FormBorderStyle.FixedDialog;
            MaximizeBox = false;
            MinimizeBox = false;
            ControlBox = false;
            StartPosition = FormStartPosition.CenterScreen;
            TopMost = true;
            ClientSize = new Size(440, 140);
            Font = SystemFonts.MessageBoxFont;
            stage.SetBounds(16, 14, 408, 20);
            bar.SetBounds(16, 40, 408, 22);
            bar.Maximum = 1000;
            bytes.SetBounds(16, 68, 408, 20);
            cancel.Text = "Cancelar";
            cancel.SetBounds(324, 96, 100, 30);
            cancel.Click += delegate { Cancel(); };
            Controls.Add(stage);
            Controls.Add(bar);
            Controls.Add(bytes);
            Controls.Add(cancel);
            FormClosing += delegate(object s, FormClosingEventArgs e) { if (!done) { e.Cancel = true; } };
        }

        public bool Cancelled { get { return cancelled; } }

        readonly object cancelGate = new object();
        bool cancelLocked;

        public void Cancel()
        {
            lock (cancelGate)
            {
                if (cancelled || cancelLocked) { return; }
                cancelled = true;
            }
            OnUi(delegate { cancel.Enabled = false; stage.Text = "Cancelando\u2026"; });
        }

        // Ends the cancellable part: false when Cancelar was already pressed (the caller rolls
        // back); true when later clicks are ignored from now on.
        public bool LockCancel()
        {
            lock (cancelGate)
            {
                if (cancelled) { return false; }
                cancelLocked = true;
            }
            OnUi(delegate { cancel.Enabled = false; });
            return true;
        }

        public void SetStage(string text) { OnUi(delegate { if (!cancelled) { stage.Text = text; } }); }

        long lastShown = -1;

        public void SetProgress(long doneBytes, long total)
        {
            if (doneBytes - lastShown < 256 * 1024 && doneBytes != total) { return; }   // throttle
            lastShown = doneBytes;
            OnUi(delegate
            {
                bar.Value = total > 0 ? (int)Math.Min(1000, doneBytes * 1000 / total) : 0;
                bytes.Text = Fs.Megabytes(doneBytes) + (total > 0 ? " de " + Fs.Megabytes(total) : "");
            });
        }

        void OnUi(Action a)
        {
            try { if (IsHandleCreated && !IsDisposed) { BeginInvoke(a); } }
            catch (InvalidOperationException) { }
        }

        // Shows the dialog and runs work(dialog) on a worker thread until it returns.
        public static void Run(string title, Action<ProgressDialog> work)
        {
            using (ProgressDialog d = new ProgressDialog(title))
            {
                Exception crash = null;
                d.Shown += delegate
                {
                    Thread t = new Thread(delegate()
                    {
                        try { work(d); }
                        catch (Exception e) { crash = e; }
                        d.done = true;
                        d.OnUi(delegate { d.Close(); });
                    });
                    t.IsBackground = true;
                    t.Start();
                };
                d.ShowDialog();
                if (crash != null) { throw new InvalidOperationException("error en la actualizaci\u00f3n", crash); }
            }
        }
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
        // passes; fails early only when the process exits. After slowMs with the process still
        // alive, onSlow runs once (balloon: it is probably updating the data). pump keeps the UI
        // alive. null on success, otherwise the reason.
        public string WaitReady(int slowMs, int timeoutMs, Action pump, Action onSlow)
        {
            Stopwatch sw = Stopwatch.StartNew();
            bool loggedUnexpected = false;
            bool slowNoticed = false;
            while (sw.ElapsedMilliseconds < timeoutMs)
            {
                if (HasExited) { return "el servidor se cerr\u00f3 al arrancar"; }
                if (!slowNoticed && sw.ElapsedMilliseconds >= slowMs)
                {
                    slowNoticed = true;
                    Log.Write("El servidor sigue vivo tras " + (slowMs / 1000) + " s sin responder: sigo esperando (hasta " +
                              (timeoutMs / 60000) + " min)");
                    if (onSlow != null) { onSlow(); }
                }
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
                    if (!loggedUnexpected)
                    {
                        loggedUnexpected = true;
                        Log.Write("Respuesta inesperada de /api/version (" + status + ")");
                    }
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
        System.Windows.Forms.Timer checkTimer;   // tests: --buscar-tras=
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

        public void ShowMigrating()
        {
            Log.Write("Globito: Actualizando tus datos");
            icon.ShowBalloonTip(15000, Program.Title, "Actualizando tus datos\u2026 puede tardar unos minutos", ToolTipIcon.Info);
        }

        public void Start(ServerProcess server, string updatedTo, int closeAfterSeconds, int checkAfterSeconds)
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
                Log.Write("Globito: POKKER se actualiz\u00f3 a " + updatedTo);
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

            if (checkAfterSeconds > 0)
            {
                // Test-only (--buscar-tras=): the same action as "Buscar actualizaciones".
                checkTimer = new System.Windows.Forms.Timer();
                checkTimer.Interval = checkAfterSeconds * 1000;
                checkTimer.Tick += delegate
                {
                    checkTimer.Stop();
                    Log.Write("PRUEBA: --buscar-tras=" + checkAfterSeconds + " -> Buscar actualizaciones");
                    Updater.CheckFromTray(this);
                };
                checkTimer.Start();
            }
        }

        public ServerProcess Server { get { return server; } }
        public bool IsClosing { get { return closing || finished; } }

        public void SetUpdateItemEnabled(bool enabled)
        {
            if (updateItem != null && !closing) { updateItem.Enabled = enabled; }
        }
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

        public void Finish(string reason)
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
                if (checkTimer != null) { checkTimer.Dispose(); }
                icon.Visible = false;
                icon.Dispose();
                invoker.Dispose();
            }
            base.Dispose(disposing);
        }
    }
}
