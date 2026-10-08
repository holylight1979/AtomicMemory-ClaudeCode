// smells v2 — 「不是 bug 但壞味道」的四個可數指標，純語法（Roslyn 語法樹、無語意模型），partial 類別跨檔合併。
//   用法：smells <rootDir> [--entry-class <類別>] [--entry-prefix <前綴>] [--wired-file <相對路徑,...>] [--test-dirs <片段,...>]
//     --entry-class  D 指標要看的類別（預設 FakeMapServer）
//     --entry-prefix 入口方法前綴（預設 Req）
//     --wired-file   「玩家路徑」的分派檔（相對 rootDir，逗號分隔）；在這些檔裡被呼叫的入口＝直接已接
//     --test-dirs    視為測試／工具路徑的片段（逗號分隔，預設 "MCP/,/Editor/,Test"）
//   A 狀態所有權散落：private 容器欄位的改動點（Add/Remove/Clear/索引賦值…）散在幾個檔、幾個方法
//   B 讀路徑長度：public 方法沿同類別委派鏈最深一條：委派跳數＋條件巢狀深度（switch 分派型會爆表，另標）
//   C 純轉接：方法體只有一行「把參數原樣丟給另一個方法」
//   D 入口可達性：直接已接／經已接入口間接可達（傳遞閉包）／只有測試路徑／只被類別內部非入口方法呼叫／沒人呼叫
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;

static class Program
{
    class ClassInfo
    {
        public string Name;
        public List<(ClassDeclarationSyntax decl, string file)> Parts = new List<(ClassDeclarationSyntax, string)>();
        public Dictionary<string, List<(MethodDeclarationSyntax m, string file)>> Methods = new Dictionary<string, List<(MethodDeclarationSyntax, string)>>();
        public Dictionary<string, (FieldDeclarationSyntax f, string file)> Fields = new Dictionary<string, (FieldDeclarationSyntax, string)>();
    }

    static readonly HashSet<string> MutatingCalls = new HashSet<string> { "Add", "Remove", "Clear", "TryAdd", "Enqueue", "Dequeue", "Push", "Pop", "AddRange", "RemoveAt", "RemoveAll", "RemoveRange", "Insert", "Release", "Set" };
    static readonly string[] ContainerTypes = { "Dictionary<", "HashSet<", "List<", "Queue<", "Stack<", "SortedDictionary<", "LinkedList<" };

    static int Main(string[] args)
    {
        string root = Path.GetFullPath(args[0]);
        string entryClass = "FakeMapServer", entryPrefix = "Req";
        var wiredFiles = new List<string>();
        var testDirs = new List<string> { "MCP/", "/Editor/", "Test" };
        for (int i = 1; i < args.Length - 1; i++)
        {
            if (args[i] == "--entry-class") entryClass = args[i + 1];
            if (args[i] == "--entry-prefix") entryPrefix = args[i + 1];
            if (args[i] == "--wired-file") wiredFiles = args[i + 1].Split(',').Select(x => x.Trim().Replace('\\', '/')).ToList();
            if (args[i] == "--test-dirs") testDirs = args[i + 1].Split(',').Select(x => x.Trim().Replace('\\', '/')).ToList();
        }
        var files = Directory.EnumerateFiles(root, "*.cs", SearchOption.AllDirectories)
            .Where(p => !p.Contains("\\bin\\") && !p.Contains("\\obj\\") && !p.Contains("auto_generate") && !p.EndsWith("Generated.cs") && !p.Contains("\\Benchmarks\\"))
            .ToList();
        var trees = new Dictionary<string, CompilationUnitSyntax>();
        foreach (var f in files) trees[f] = CSharpSyntaxTree.ParseText(File.ReadAllText(f)).GetCompilationUnitRoot();
        Console.WriteLine("smells v2  files parsed: " + trees.Count);

        var classes = new Dictionary<string, ClassInfo>();
        foreach (var kv in trees)
            foreach (var c in kv.Value.DescendantNodes().OfType<ClassDeclarationSyntax>())
            {
                if (!classes.TryGetValue(c.Identifier.Text, out var ci)) classes[c.Identifier.Text] = ci = new ClassInfo { Name = c.Identifier.Text };
                ci.Parts.Add((c, kv.Key));
                foreach (var m in c.Members.OfType<MethodDeclarationSyntax>())
                {
                    if (!ci.Methods.TryGetValue(m.Identifier.Text, out var l)) ci.Methods[m.Identifier.Text] = l = new List<(MethodDeclarationSyntax, string)>();
                    l.Add((m, kv.Key));
                }
                foreach (var f in c.Members.OfType<FieldDeclarationSyntax>())
                    foreach (var v in f.Declaration.Variables) ci.Fields[v.Identifier.Text] = (f, kv.Key);
            }

        string Rel(string p) => Path.GetRelativePath(root, p).Replace('\\', '/');

        // ── A ──
        Console.WriteLine("\n=== A. container fields whose mutation sites spread across files (top 25; flag: files>=3 or sites>=6) ===");
        var aRows = new List<(string cls, string field, int sites, int fileCount, int methodCount, string filesList)>();
        foreach (var ci in classes.Values)
        {
            if (ci.Parts.Count < 2) continue;
            foreach (var fkv in ci.Fields)
            {
                string typeText = fkv.Value.f.Declaration.Type.ToString();
                if (!ContainerTypes.Any(t => typeText.StartsWith(t))) continue;
                if (!fkv.Value.f.Modifiers.Any(SyntaxKind.PrivateKeyword)) continue;
                string name = fkv.Key;
                var sites = new List<(string file, string method)>();
                foreach (var part in ci.Parts)
                    foreach (var node in part.decl.DescendantNodes())
                    {
                        bool hit = false;
                        if (node is InvocationExpressionSyntax inv && inv.Expression is MemberAccessExpressionSyntax ma && ma.Expression is IdentifierNameSyntax id && id.Identifier.Text == name && MutatingCalls.Contains(ma.Name.Identifier.Text)) hit = true;
                        else if (node is AssignmentExpressionSyntax asg && asg.Left is ElementAccessExpressionSyntax ea && ea.Expression is IdentifierNameSyntax id2 && id2.Identifier.Text == name) hit = true;
                        if (!hit) continue;
                        var method = node.Ancestors().OfType<MethodDeclarationSyntax>().FirstOrDefault();
                        sites.Add((part.file, method != null ? method.Identifier.Text : "<field-init>"));
                    }
                if (sites.Count == 0) continue;
                aRows.Add((ci.Name, name, sites.Count, sites.Select(s => s.file).Distinct().Count(), sites.Select(s => s.method).Distinct().Count(), string.Join(",", sites.Select(s => Path.GetFileName(s.file)).Distinct().Take(6))));
            }
        }
        Console.WriteLine("container fields in partial classes: " + aRows.Count + "  flagged: " + aRows.Count(r => r.fileCount >= 3 || r.sites >= 6));
        foreach (var r in aRows.OrderByDescending(r => r.fileCount).ThenByDescending(r => r.sites).Take(25))
            Console.WriteLine($"  {r.cls}.{r.field,-28} sites={r.sites,3} files={r.fileCount} methods={r.methodCount}  [{r.filesList}]");

        // ── B ──
        Console.WriteLine("\n=== B. deepest delegation path per public/internal method, across partials (top 20; switch-dispatchers flagged) ===");
        var bRows = new List<(string cls, string method, int del, int nest, int bends, bool dispatcher, string chain)>();
        foreach (var ci in classes.Values)
        {
            if (ci.Parts.Count < 2) continue;
            foreach (var mk in ci.Methods)
            {
                var (m, file) = mk.Value[0];
                if (!m.Modifiers.Any(SyntaxKind.PublicKeyword) && !m.Modifiers.Any(SyntaxKind.InternalKeyword)) continue;
                var chain = new List<string>();
                var res = Walk(ci, m, new HashSet<string>(), chain, 0);
                SyntaxNode body = (SyntaxNode)m.Body ?? m.ExpressionBody;
                bool dispatcher = body != null && body.DescendantNodes().OfType<SwitchStatementSyntax>().Any(s => s.Sections.Count >= 8);
                bRows.Add((ci.Name, mk.Key, res.del, res.nest, res.del + res.nest, dispatcher, string.Join(">", chain.Take(8))));
            }
        }
        foreach (var r in bRows.OrderByDescending(r => r.bends).Take(20))
            Console.WriteLine($"  {r.cls}.{r.method,-30} bends={r.bends,2} (deleg {r.del}, nest {r.nest}){(r.dispatcher ? " [switch-dispatcher]" : "")}  {r.chain}");
        var dist = bRows.Where(r => !r.dispatcher).GroupBy(r => r.bends > 6 ? ">6" : r.bends > 3 ? "4-6" : "<=3").ToDictionary(g => g.Key, g => g.Count());
        Console.WriteLine("  distribution (excluding switch-dispatchers " + bRows.Count(r => r.dispatcher) + "): " + string.Join("  ", dist.OrderBy(k => k.Key).Select(k => k.Key + ":" + k.Value)));

        // ── C ──
        Console.WriteLine("\n=== C. pure forwarding methods (body = single call, args passed through) ===");
        var cRows = new List<string>();
        foreach (var kv in trees)
            foreach (var m in kv.Value.DescendantNodes().OfType<MethodDeclarationSyntax>())
            {
                InvocationExpressionSyntax call = null;
                if (m.Body != null && m.Body.Statements.Count == 1)
                {
                    if (m.Body.Statements[0] is ExpressionStatementSyntax es && es.Expression is InvocationExpressionSyntax i1) call = i1;
                    else if (m.Body.Statements[0] is ReturnStatementSyntax rs && rs.Expression is InvocationExpressionSyntax i2) call = i2;
                }
                else if (m.ExpressionBody != null && m.ExpressionBody.Expression is InvocationExpressionSyntax i3) call = i3;
                if (call == null || m.Modifiers.Any(SyntaxKind.OverrideKeyword)) continue;
                var pnames = new HashSet<string>(m.ParameterList.Parameters.Select(p => p.Identifier.Text));
                bool passthrough = call.ArgumentList.Arguments.All(a => a.Expression is IdentifierNameSyntax an && pnames.Contains(an.Identifier.Text) || a.Expression is LiteralExpressionSyntax || a.Expression is ThisExpressionSyntax);
                if (!passthrough) continue;
                cRows.Add($"{Rel(kv.Key)}:{m.GetLocation().GetLineSpan().StartLinePosition.Line + 1} {m.Identifier.Text} -> {call.Expression}");
            }
        Console.WriteLine("count: " + cRows.Count);
        foreach (var s in cRows.Take(15)) Console.WriteLine("  " + s);

        // ── D ──
        Console.WriteLine($"\n=== D. {entryClass}.{entryPrefix}* entry reachability (wired files: {(wiredFiles.Count == 0 ? "-" : string.Join(",", wiredFiles))}; test dirs: {string.Join(",", testDirs)}) ===");
        if (!classes.TryGetValue(entryClass, out var ec)) { Console.WriteLine("entry class not found"); return 0; }
        var classFiles = new HashSet<string>(ec.Parts.Select(p => p.file));
        var entries = ec.Methods.Where(k => k.Key.StartsWith(entryPrefix) && k.Value[0].m.Modifiers.Any(SyntaxKind.PublicKeyword)).Select(k => k.Key).ToHashSet();
        // 呼叫索引：入口名 → (檔, 所在方法名)
        var callers = new Dictionary<string, List<(string file, string method)>>();
        foreach (var kv in trees)
            foreach (var inv in kv.Value.DescendantNodes().OfType<InvocationExpressionSyntax>())
            {
                string n = inv.Expression is MemberAccessExpressionSyntax ma ? ma.Name.Identifier.Text : inv.Expression is IdentifierNameSyntax idn ? idn.Identifier.Text : null;
                if (n == null || !entries.Contains(n)) continue;
                var enclosing = inv.Ancestors().OfType<MethodDeclarationSyntax>().FirstOrDefault();
                if (!callers.TryGetValue(n, out var l)) callers[n] = l = new List<(string, string)>();
                l.Add((kv.Key, enclosing != null ? enclosing.Identifier.Text : "<non-method>"));
            }
        bool IsWiredFile(string f) { string r = Rel(f); return wiredFiles.Any(w => r.EndsWith(w, StringComparison.OrdinalIgnoreCase)); }
        bool IsTestFile(string f) { string r = Rel(f); return testDirs.Any(t => r.Contains(t)); }
        // 第 0 層：被 wired 檔直接呼叫；之後：被已接入口（含間接）在類別內呼叫 → 傳遞閉包
        var direct = entries.Where(e => callers.TryGetValue(e, out var l) && l.Any(c => IsWiredFile(c.file))).ToHashSet();
        var reach = new HashSet<string>(direct); bool grew = true;
        while (grew)
        {
            grew = false;
            foreach (var e in entries.Except(reach).ToList())
                if (callers.TryGetValue(e, out var l) && l.Any(c => classFiles.Contains(c.file) && reach.Contains(c.method))) { reach.Add(e); grew = true; }
        }
        var rows = new List<(string cls, string name, string callerSummary)>();
        int nDirect = 0, nIndirect = 0, nTestOnly = 0, nInternal = 0, nNone = 0;
        foreach (var e in entries.OrderBy(x => x))
        {
            callers.TryGetValue(e, out var l); l = l ?? new List<(string, string)>();
            var outside = l.Where(c => !classFiles.Contains(c.file)).ToList();
            string cls;
            if (direct.Contains(e)) { cls = "wired-direct"; nDirect++; }
            else if (reach.Contains(e)) { cls = "wired-indirect"; nIndirect++; }
            else if (outside.Count > 0 && outside.All(c => IsTestFile(c.file))) { cls = "test-only"; nTestOnly++; }
            else if (outside.Count == 0 && l.Count > 0) { cls = "internal-only"; nInternal++; }
            else if (l.Count == 0) { cls = "none"; nNone++; }
            else { cls = "other-caller"; }
            string summary = string.Join(" ", l.GroupBy(c => (classFiles.Contains(c.file) ? "class:" + c.method : Rel(c.file).Split('/')[0] + "/")).Select(g => g.Key + (g.Count() > 1 ? "x" + g.Count() : "")).Take(5));
            rows.Add((cls, e, summary));
        }
        Console.WriteLine($"entries: {entries.Count}  wired-direct: {nDirect}  wired-indirect: {nIndirect}  test-only: {nTestOnly}  internal-only: {nInternal}  none: {nNone}");
        foreach (var r in rows.Where(r => r.cls != "wired-direct")) Console.WriteLine($"  {r.cls,-15} {r.name,-28} {r.callerSummary}");
        return 0;
    }

    static (int del, int nest) Walk(ClassInfo ci, MethodDeclarationSyntax m, HashSet<string> visited, List<string> chain, int depth)
    {
        string key = m.Identifier.Text;
        if (!visited.Add(key) || depth > 12) return (0, 0);
        chain.Add(key);
        SyntaxNode body = (SyntaxNode)m.Body ?? m.ExpressionBody;
        if (body == null) return (0, 0);
        int maxNest = 0;
        foreach (var n in body.DescendantNodes())
        {
            if (!(n is IfStatementSyntax || n is ConditionalExpressionSyntax || n is SwitchStatementSyntax)) continue;
            int d = 1; var p = n.Parent;
            while (p != null && p != body) { if (p is IfStatementSyntax || p is SwitchStatementSyntax || p is ConditionalExpressionSyntax) d++; p = p.Parent; }
            if (d > maxNest) maxNest = d;
        }
        int bestDel = 0, bestNest = 0; List<string> bestChain = null; bool any = false;
        foreach (var inv in body.DescendantNodes().OfType<InvocationExpressionSyntax>())
        {
            string name = inv.Expression is IdentifierNameSyntax id ? id.Identifier.Text : inv.Expression is MemberAccessExpressionSyntax ma && ma.Expression is ThisExpressionSyntax ? ma.Name.Identifier.Text : null;
            if (name == null || !ci.Methods.TryGetValue(name, out var cands)) continue;
            var subChain = new List<string>();
            var sub = Walk(ci, cands[0].m, new HashSet<string>(visited), subChain, depth + 1);
            int score = 1 + sub.del + sub.nest;
            if (!any || score > bestDel + bestNest) { any = true; bestDel = 1 + sub.del; bestNest = sub.nest; bestChain = subChain; }
        }
        if (any) chain.AddRange(bestChain);
        return (bestDel, maxNest + bestNest);
    }
}
