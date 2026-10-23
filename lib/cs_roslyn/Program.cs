// cs_roslyn：用 Roslyn 語法樹抓一批 .cs 的語法事實，給 lib/cs_roslyn.py 組成 reading_path_lang 的 Module。
// 怎麼跑：stdin {"files":[{"rel","text"}]} → stdout {"modules":[每檔一筆]}；由 lib/cs_roslyn.py 編譯與呼叫，不手動跑。
// 只抓語法、不做分類：呼叫的種類、引數是不是函式參照、雜訊呼叫、多載改簽章，都在 Python 端照輕量解析同一套規則做。
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;

var input = JsonNode.Parse(Console.OpenStandardInput());
var modules = new JsonArray();
foreach (var f in input["files"].AsArray())
{
    var rel = f["rel"].GetValue<string>();
    try { modules.Add(Facts.Module(rel, f["text"].GetValue<string>())); }
    catch (Exception e) { modules.Add(new JsonObject { ["file"] = rel, ["error"] = $"{e.GetType().Name}: {e.Message}" }); }
}
using (var stdout = Console.OpenStandardOutput())
using (var writer = new Utf8JsonWriter(stdout))
    new JsonObject { ["modules"] = modules }.WriteTo(writer);

static class Facts
{
    static readonly HashSet<string> ContainerAdd = new() { "Add", "Insert", "Push", "Enqueue", "AddLast", "AddFirst" };
    static readonly Regex Lower = new(@"^[a-z_]\w*$");

    public static JsonObject Module(string rel, string text)
    {
        var root = CSharpSyntaxTree.ParseText(text, new CSharpParseOptions(LanguageVersion.Preview)).GetCompilationUnitRoot();
        var classes = new JsonArray();
        foreach (var t in root.DescendantNodes().OfType<TypeDeclarationSyntax>())
            if (t is ClassDeclarationSyntax or StructDeclarationSyntax or InterfaceDeclarationSyntax or RecordDeclarationSyntax
                && !t.OpenBraceToken.IsKind(SyntaxKind.None))       // record R(int X); 沒有本體：輕量解析也不收
                classes.Add(Type(t));
        var statics = new JsonArray();
        foreach (var u in root.DescendantNodes().OfType<UsingDirectiveSyntax>())
            if (u.StaticKeyword.IsKind(SyntaxKind.StaticKeyword) && u.Name != null)
                statics.Add(Squash(u.Name.ToString()));
        return new JsonObject { ["file"] = rel, ["static_usings"] = statics, ["classes"] = classes };
    }

    static JsonObject Type(TypeDeclarationSyntax t)
    {
        var fields = new JsonObject();
        var events = new JsonArray();
        var funcs = new JsonArray();
        foreach (var m in t.Members)
        {
            switch (m)
            {
                case MethodDeclarationSyntax x:
                    funcs.Add(Func(m, x.Identifier.Text, x.ParameterList, x.Body, x.ExpressionBody)); break;
                case ConstructorDeclarationSyntax x:
                    funcs.Add(Func(m, x.Identifier.Text, x.ParameterList, x.Body, x.ExpressionBody)); break;
                case PropertyDeclarationSyntax x:
                    fields[x.Identifier.Text] = SimpleType(x.Type);
                    if (x.ExpressionBody != null || (x.AccessorList?.Accessors.Any(a => a.Body != null || a.ExpressionBody != null) ?? false))
                        funcs.Add(Prop(x));
                    break;
                case FieldDeclarationSyntax x:
                    foreach (var v in x.Declaration.Variables) fields[v.Identifier.Text] = SimpleType(x.Declaration.Type);
                    break;
                case EventFieldDeclarationSyntax x:
                    foreach (var v in x.Declaration.Variables) { fields[v.Identifier.Text] = SimpleType(x.Declaration.Type); events.Add(v.Identifier.Text); }
                    break;
                case EventDeclarationSyntax x:
                    fields[x.Identifier.Text] = SimpleType(x.Type); events.Add(x.Identifier.Text); break;
            }
        }
        var bases = new JsonArray();
        foreach (var b in t.BaseList?.Types ?? default) bases.Add(SimpleType(b.Type));
        return new JsonObject { ["name"] = t.Identifier.Text, ["partial"] = t.Modifiers.Any(SyntaxKind.PartialKeyword),
                                ["bases"] = bases, ["fields"] = fields, ["events"] = events, ["funcs"] = funcs };
    }

    static JsonObject Func(MemberDeclarationSyntax m, string name, ParameterListSyntax pl, BlockSyntax body, ArrowExpressionClauseSyntax arrow)
    {
        var parts = new List<SyntaxNode>();
        if (body != null) parts.Add(body);
        if (arrow != null) parts.Add(arrow.Expression);
        var stmts = body?.Statements.Where(Ends).ToList() ?? new List<StatementSyntax>();
        var o = Head(m, name, pl, false, body == null && arrow == null, body != null && body.Statements.Count == 0);
        Body(o, parts, arrow != null ? 1 : stmts.Count, stmts.Count(Move));
        return o;
    }

    static JsonObject Prop(PropertyDeclarationSyntax p)
    {
        var parts = new List<SyntaxNode>();
        var stmts = new List<StatementSyntax>();
        int count = p.ExpressionBody != null ? 1 : 0;
        if (p.ExpressionBody != null) parts.Add(p.ExpressionBody.Expression);
        foreach (var a in p.AccessorList?.Accessors ?? default)
        {
            if (a.Body != null) { parts.Add(a.Body); stmts.AddRange(a.Body.Statements.Where(Ends)); }
            if (a.ExpressionBody != null) parts.Add(a.ExpressionBody.Expression);
        }
        if (p.AccessorList != null)   // 輕量解析把屬性 get／set 裡每個分號都當一句
            count = p.AccessorList.DescendantTokens().Count(k => k.IsKind(SyntaxKind.SemicolonToken));
        var o = Head(p, p.Identifier.Text, null, true, false, false);
        Body(o, parts, count, stmts.Count(Move));
        return o;
    }

    static JsonObject Head(MemberDeclarationSyntax m, string name, ParameterListSyntax pl, bool prop, bool declared, bool empty)
    {
        var span = m.GetLocation().GetLineSpan();
        var mods = new JsonArray();
        foreach (var k in m.Modifiers) mods.Add(k.Text);
        var ps = new JsonArray();
        foreach (var p in pl?.Parameters ?? default)
        {
            var type = p.Type == null ? "" : Regex.Replace(p.Type.ToString(), @"\s*([<>,\[\]])\s*", "$1");
            var text = string.Join(" ", p.Modifiers.Select(k => k.Text).Append(type).Where(s => s != ""));
            ps.Add(new JsonObject { ["name"] = p.Identifier.Text, ["type"] = p.Type == null ? "" : SimpleType(p.Type), ["text"] = text });
        }
        var conditional = m.AttributeLists.SelectMany(a => a.Attributes).Any(a =>
            Squash(a.Name.ToString()) is "Conditional" or "ConditionalAttribute" or "System.Diagnostics.Conditional" or "System.Diagnostics.ConditionalAttribute");
        return new JsonObject { ["name"] = name, ["line"] = span.StartLinePosition.Line + 1, ["end"] = span.EndLinePosition.Line + 1,
                                ["mods"] = mods, ["params"] = ps, ["prop"] = prop, ["declared"] = declared, ["empty"] = empty,
                                ["conditional"] = conditional };
    }

    // ─── 本體：呼叫、讀屬性、區域變數、指定、訂閱 ───────────────────────────────────

    static void Body(JsonObject o, List<SyntaxNode> parts, int stmts, int moves)
    {
        var calls = new List<(int pos, JsonObject c)>();
        var props = new List<(int pos, JsonObject p)>();
        var locals = new JsonArray();
        var inline = new JsonArray();
        var assigns = new JsonArray();
        var subs = new JsonArray();
        var stores = new Dictionary<string, int>();
        var escaped = new SortedSet<string>();
        int opaque = 0;
        bool compound = false;
        void Store(string name, int k) => stores[name] = stores.GetValueOrDefault(name) + k;

        foreach (var n in parts.SelectMany(p => p.DescendantNodesAndSelf()))
        {
            compound |= n is IfStatementSyntax or ForStatementSyntax or CommonForEachStatementSyntax or WhileStatementSyntax
                or DoStatementSyntax or SwitchStatementSyntax or SwitchExpressionSyntax or TryStatementSyntax
                or LockStatementSyntax or UsingStatementSyntax;
            switch (n)
            {
                case InvocationExpressionSyntax inv:
                    if (Call(inv) is var (pos, c) && c != null) calls.Add((pos, c));
                    else opaque++;
                    Escapes(inv, escaped);
                    if (inv.Expression is MemberAccessExpressionSyntax { Name.Identifier.Text: "AddListener" } ma
                        && inv.ArgumentList.Arguments.Count == 1 && Chain(ma.Expression) is string lhs
                        && Chain(inv.ArgumentList.Arguments[0].Expression) is string rhs)
                        subs.Add(new JsonObject { ["lhs"] = lhs, ["rhs"] = rhs });
                    break;
                case ObjectCreationExpressionSyntax oc when oc.ArgumentList != null:
                    calls.Add((oc.SpanStart, Entry(true, SimpleType(oc.Type), "", false, oc.ArgumentList, oc)));
                    break;
                case VariableDeclaratorSyntax v when v.Initializer != null && v.Parent is VariableDeclarationSyntax d:
                    var value = v.Initializer.Value;
                    var lambda = value is AnonymousFunctionExpressionSyntax;
                    locals.Add(new JsonObject { ["var"] = v.Identifier.Text, ["var_kw"] = d.Type.IsVar, ["type"] = PlainType(d.Type),
                                                ["new"] = value is ObjectCreationExpressionSyntax oc2 ? SimpleType(oc2.Type) : "",
                                                ["init"] = Chain(value) ?? "", ["lambda"] = lambda });
                    if (lambda) inline.Add(v.Identifier.Text);
                    Store(v.Identifier.Text, 1);
                    break;
                case LocalFunctionStatementSyntax lf:
                    inline.Add(lf.Identifier.Text); break;
                case AssignmentExpressionSyntax a when !(a.Parent is InitializerExpressionSyntax):
                    if (a.Left is IdentifierNameSyntax id)
                        Store(id.Identifier.Text, a.IsKind(SyntaxKind.SimpleAssignmentExpression) ? 1
                              : a.IsKind(SyntaxKind.AddAssignmentExpression) || a.IsKind(SyntaxKind.SubtractAssignmentExpression) ? 2 : 0);
                    if (a.IsKind(SyntaxKind.SimpleAssignmentExpression))   // lhs 空＝別的物件的成員或下標（右邊的區域變數照樣算逃逸）
                        assigns.Add(new JsonObject { ["lhs"] = Target(a.Left) ?? "",
                                                     ["new"] = a.Right is ObjectCreationExpressionSyntax oc3 ? SimpleType(oc3.Type) : "",
                                                     ["rhs"] = a.Right is IdentifierNameSyntax r ? r.Identifier.Text : "" });
                    if (a.IsKind(SyntaxKind.AddAssignmentExpression) && Chain(a.Left) is string sl && Chain(a.Right) is string sr)
                        subs.Add(new JsonObject { ["lhs"] = sl, ["rhs"] = sr });
                    break;
                case ArgumentSyntax arg when !arg.RefKindKeyword.IsKind(SyntaxKind.None) && !arg.RefKindKeyword.IsKind(SyntaxKind.InKeyword):
                    if (arg.Expression is IdentifierNameSyntax rid) Store(rid.Identifier.Text, 2);
                    if (arg.Expression is DeclarationExpressionSyntax { Designation: SingleVariableDesignationSyntax sv }) Store(sv.Identifier.Text, 2);
                    break;
                case InitializerExpressionSyntax init when init.Parent is BaseObjectCreationExpressionSyntax or ArrayCreationExpressionSyntax
                                                       or ImplicitArrayCreationExpressionSyntax:
                    foreach (var name in init.DescendantNodes().OfType<IdentifierNameSyntax>())
                        if (Lower.IsMatch(name.Identifier.Text) && !(name.Parent is MemberAccessExpressionSyntax pm && pm.Name == name))
                            escaped.Add(name.Identifier.Text);
                    break;
            }
            if (n is ExpressionSyntax e && PropUse(e) is (string recv, string pname))
                props.Add((e.SpanStart, new JsonObject { ["recv"] = recv, ["name"] = pname }));
        }
        o["calls"] = new JsonArray(calls.OrderBy(x => x.pos).Select(x => (JsonNode)x.c).ToArray());
        o["props"] = new JsonArray(props.OrderBy(x => x.pos).Select(x => (JsonNode)x.p).ToArray());
        o["opaque"] = opaque;
        o["stmts"] = stmts;
        o["moves"] = moves;
        o["compound"] = compound;
        o["locals"] = locals;
        o["inline"] = inline;
        o["stores"] = new JsonObject(stores.Where(kv => kv.Value > 0).Select(kv => KeyValuePair.Create(kv.Key, (JsonNode)kv.Value)));
        o["assigns"] = assigns;
        o["escaped"] = new JsonArray(escaped.Select(s => (JsonNode)s).ToArray());
        o["receiver_only"] = new JsonArray(ReceiverOnly(parts).Select(s => (JsonNode)s).ToArray());
        o["subs"] = subs;
    }

    // 一個呼叫點 → (排序位置, 事實)；對象是算出來的值（下標、呼叫結果、括號）→ (0, null)，算一次看不到對象的呼叫
    static (int, JsonObject) Call(InvocationExpressionSyntax inv)
    {
        switch (inv.Expression)
        {
            case SimpleNameSyntax s:
                return (s.SpanStart, Entry(false, s.Identifier.Text, "", false, inv.ArgumentList, inv));
            case MemberAccessExpressionSyntax ma when ma.IsKind(SyntaxKind.SimpleMemberAccessExpression):
                var recv = Chain(ma.Expression);
                return recv != null ? (ma.SpanStart, Entry(false, ma.Name.Identifier.Text, recv, false, inv.ArgumentList, inv))
                                    : (ma.Name.SpanStart, Entry(false, ma.Name.Identifier.Text, "", true, inv.ArgumentList, inv));
            case MemberBindingExpressionSyntax mb:          // a?.M(…)
                var owner = Owner(mb);
                var chain = owner == null ? null : Chain(owner);
                return chain != null ? (owner.SpanStart, Entry(false, mb.Name.Identifier.Text, chain, false, inv.ArgumentList, inv))
                                     : (mb.Name.SpanStart, Entry(false, mb.Name.Identifier.Text, "", true, inv.ArgumentList, inv));
        }
        return (0, null);
    }

    static JsonObject Entry(bool isNew, string name, string recv, bool onResult, ArgumentListSyntax args, SyntaxNode at)
    {
        var texts = new JsonArray();
        foreach (var a in args?.Arguments ?? default) texts.Add(ArgText(a));
        var (scoped, shadow) = Scope(at);
        return new JsonObject { ["new"] = isNew, ["name"] = name, ["recv"] = recv, ["on_result"] = onResult, ["args"] = texts,
                                ["scoped"] = scoped, ["shadow"] = shadow };
    }

    // 引數文字照輕量解析看到的樣子：字串與字元字面值是空的，具名引數寫成「名字: 值」，ref／out／in 帶在前面
    static string ArgText(ArgumentSyntax a)
    {
        var value = a.Expression is LiteralExpressionSyntax l && (l.IsKind(SyntaxKind.StringLiteralExpression) || l.IsKind(SyntaxKind.CharacterLiteralExpression))
                    || a.Expression is InterpolatedStringExpressionSyntax ? "" : a.Expression.ToString().Replace('\n', ' ').Replace('\r', ' ');
        var refkind = a.RefKindKeyword.IsKind(SyntaxKind.None) ? "" : a.RefKindKeyword.Text + " ";
        return (a.NameColon != null ? a.NameColon.Name.Identifier.Text + ": " : "") + refkind + value;
    }

    // 呼叫點在 lambda、匿名方法、區域函式裡 → (true, 那些構件的參數名)：模型沒建那一層的參數與綁定
    static (bool, JsonArray) Scope(SyntaxNode at)
    {
        var names = new JsonArray();
        bool scoped = false;
        foreach (var a in at.Ancestors())
        {
            if (a is MemberDeclarationSyntax) break;
            IEnumerable<ParameterSyntax> ps = a switch
            {
                SimpleLambdaExpressionSyntax x => new[] { x.Parameter },
                ParenthesizedLambdaExpressionSyntax x => x.ParameterList.Parameters,
                AnonymousMethodExpressionSyntax x => x.ParameterList?.Parameters ?? default(SeparatedSyntaxList<ParameterSyntax>),
                LocalFunctionStatementSyntax x => x.ParameterList.Parameters,
                _ => null,
            };
            if (ps == null) continue;
            scoped = true;
            foreach (var p in ps) names.Add(p.Identifier.Text);
        }
        return (scoped, names);
    }

    static void Escapes(InvocationExpressionSyntax inv, SortedSet<string> escaped)
    {
        var name = inv.Expression switch { MemberAccessExpressionSyntax m => m.Name.Identifier.Text, MemberBindingExpressionSyntax b => b.Name.Identifier.Text, _ => "" };
        var args = inv.ArgumentList.Arguments;
        if (ContainerAdd.Contains(name) && args.Count is 1 or 2 && args[^1].Expression is IdentifierNameSyntax id && Lower.IsMatch(id.Identifier.Text))
            escaped.Add(id.Identifier.Text);
    }

    // 剛 new 出來的區域變數：之後每一次出現都只是 w.M(…)／w?.M(…) 的接收者 → 列名
    static IEnumerable<string> ReceiverOnly(List<SyntaxNode> parts)
    {
        var all = parts.SelectMany(p => p.DescendantNodesAndSelf()).ToList();
        var builds = all.OfType<VariableDeclaratorSyntax>().Where(v => v.Initializer?.Value is ObjectCreationExpressionSyntax).ToList();
        foreach (var name in builds.Select(v => v.Identifier.Text).Distinct())
        {
            if (!Lower.IsMatch(name) || builds.Count(v => v.Identifier.Text == name) != 1) continue;
            var build = builds.First(v => v.Identifier.Text == name).Identifier;
            var ok = parts.SelectMany(p => p.DescendantTokens()).Where(t => t.IsKind(SyntaxKind.IdentifierToken) && t.Text == name && t != build)
                .All(t => t.Parent is IdentifierNameSyntax id && (IsMemberName(id) || IsCallReceiver(id)));
            if (ok) yield return name;
        }
    }

    static bool IsMemberName(IdentifierNameSyntax id) =>
        id.Parent is MemberAccessExpressionSyntax m && m.Name == id || id.Parent is MemberBindingExpressionSyntax;

    static bool IsCallReceiver(IdentifierNameSyntax id) =>
        id.Parent is MemberAccessExpressionSyntax m && m.Expression == id && m.Parent is InvocationExpressionSyntax i && i.Expression == m
        || id.Parent is ConditionalAccessExpressionSyntax c && c.Expression == id
           && c.WhenNotNull is InvocationExpressionSyntax { Expression: MemberBindingExpressionSyntax };

    // 讀寫屬性：大寫開頭、沒被呼叫、不在型別位置的名字或 a.B 鏈（只收整條鏈最外層那一個）→ (接收者, 名字)
    static (string, string)? PropUse(ExpressionSyntax e)
    {
        if (e.Parent is MemberAccessExpressionSyntax pm && (pm.Expression == e || pm.Name == e)) return null;
        if (e.Parent is InvocationExpressionSyntax pi && pi.Expression == e) return null;
        if (e.Parent is ConditionalAccessExpressionSyntax pc && pc.Expression == e) return null;
        if (e.Parent is NameColonSyntax or NameEqualsSyntax or QualifiedNameSyntax or AliasQualifiedNameSyntax or MemberBindingExpressionSyntax)
            return null;
        string recv, name;
        switch (e)
        {
            case IdentifierNameSyntax id when !SyntaxFacts.IsInTypeOnlyContext(id):
                recv = ""; name = id.Identifier.Text; break;
            case MemberAccessExpressionSyntax ma when ma.IsKind(SyntaxKind.SimpleMemberAccessExpression) && ma.Name is IdentifierNameSyntax n
                                                     && Chain(ma.Expression) is string r:
                recv = r; name = n.Identifier.Text; break;
            case MemberBindingExpressionSyntax mb when mb.Name is IdentifierNameSyntax n2 && Owner(mb) is ExpressionSyntax ow && Chain(ow) is string r2:
                recv = r2; name = n2.Identifier.Text; break;
            default:
                return null;
        }
        return char.IsUpper(name[0]) ? (recv, name) : null;
    }

    // ─── 寫法正規化 ─────────────────────────────────────────────────────────

    // 簡單接收者鏈 a.b.c／this.x／base.x／string（a?.b 的 ?. 也算）→ "a.b.c"；中間有呼叫、下標、泛型 → null
    static string Chain(ExpressionSyntax e) => e switch
    {
        IdentifierNameSyntax x => x.Identifier.Text,
        ThisExpressionSyntax => "this",
        BaseExpressionSyntax => "base",
        PredefinedTypeSyntax x => x.Keyword.Text,
        MemberAccessExpressionSyntax x when x.IsKind(SyntaxKind.SimpleMemberAccessExpression) && x.Name is IdentifierNameSyntax n
            => Chain(x.Expression) is string s ? s + "." + n.Identifier.Text : null,
        MemberBindingExpressionSyntax x when x.Name is IdentifierNameSyntax n
            => Owner(x) is ExpressionSyntax o && Chain(o) is string s ? s + "." + n.Identifier.Text : null,
        _ => null,
    };

    // a?.b 的 a：最近一個 WhenNotNull 包住 n 的 ?. 運算式
    static ExpressionSyntax Owner(SyntaxNode n) =>
        n.Ancestors().OfType<ConditionalAccessExpressionSyntax>().FirstOrDefault(c => c.WhenNotNull.Span.Contains(n.Span))?.Expression;

    // 指定的左邊是欄位寫法（x 或 this.x）→ 名字；其餘（a.b、下標）→ null
    static string Target(ExpressionSyntax e) => e switch
    {
        IdentifierNameSyntax x => x.Identifier.Text,
        MemberAccessExpressionSyntax { Expression: ThisExpressionSyntax, Name: IdentifierNameSyntax n } => n.Identifier.Text,
        _ => null,
    };

    // 型別 → 輕量解析記的那種短名：去命名空間、泛型、?；陣列留 []
    static string SimpleType(TypeSyntax t) => t switch
    {
        null => "",
        SimpleNameSyntax x => x.Identifier.Text,
        QualifiedNameSyntax x => SimpleType(x.Right),
        AliasQualifiedNameSyntax x => SimpleType(x.Name),
        NullableTypeSyntax x => SimpleType(x.ElementType),
        ArrayTypeSyntax x => SimpleType(x.ElementType) + string.Concat(x.RankSpecifiers.Select(r => Squash(r.ToString()))),
        PredefinedTypeSyntax x => x.Keyword.Text,
        RefTypeSyntax x => SimpleType(x.Type),
        _ => Squash(t.ToString()),
    };

    // 區域變數宣告的型別只在是名字（Foo、List<T>、A.Foo）時才記；var、陣列、可為 null、內建型別回空
    static string PlainType(TypeSyntax t) => t is SimpleNameSyntax or QualifiedNameSyntax or AliasQualifiedNameSyntax && !t.IsVar ? SimpleType(t) : "";

    // 以分號結尾的一句（輕量解析數句子的方式：複合語句、區塊、區域函式不算一句）
    static bool Ends(StatementSyntax s) => s.GetLastToken().IsKind(SyntaxKind.SemicolonToken);

    // 宣告區域變數只換個名字（var y = x.z;、int n = 0;）：轉手函式的句數不算它
    static bool Move(StatementSyntax s) =>
        s is LocalDeclarationStatementSyntax { Declaration.Variables.Count: 1 } ld && ld.Modifiers.Count == 0
        && ld.UsingKeyword.IsKind(SyntaxKind.None) && ld.Declaration.Variables[0] is { Initializer: not null } v
        && Lower.IsMatch(v.Identifier.Text)
        && (Chain(v.Initializer.Value) != null || v.Initializer.Value is LiteralExpressionSyntax lit
            && !lit.IsKind(SyntaxKind.StringLiteralExpression) && !lit.IsKind(SyntaxKind.CharacterLiteralExpression));

    static string Squash(string s) => Regex.Replace(s, @"\s+", "");
}
