<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/plugins/mods/gallery | lastmod: 2026-10-27 | section: Plugins / Mods -->
> 來源：https://code.claude.com/docs/zh-TW/plugins/mods/gallery（官方 zh-TW，lastmod 2026-10-27）｜分類：Plugins › Mods｜EN 摘要：See the interface elements a Claude Code mod can draw, such as text, buttons, fields, Markdown, code, and diffs, with sample code and terminal screenshots.

# Mod 介面圖庫

> 查看 Claude Code mod 可以繪製的介面元素，例如文字、按鈕、欄位、Markdown、程式碼和差異，並附有範例程式碼和終端機螢幕截圖。

Mod 使用元素來繪製其介面：文字、方塊、按鈕、欄位，以及一些會替您格式化內容的元素。此處的範例展示了繪製元素的程式碼，大多數範例還附有在終端機窗格中呈現結果的螢幕截圖，讓您可以依外觀挑選元素。

若要了解繪製的運作方式，請從[在介面中繪製](https://code.claude.com/docs/zh-TW/plugins/mods/interface.md)開始。如需主要 props 以及哪些應用程式會繪製各個元素，請參閱[元素參考](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#elements)。[型別宣告](https://code.claude.com/docs/zh-TW/plugins/mods/create.md#get-the-types-for-your-build)列出了所有 props。

## 試用範例

本頁的範例是程式碼片段，而非完整的 mod。每個範例都是一個元素及其內部巢狀內容的程式碼。

若要在您自己的終端機中查看範例，請依照以下步驟建立小型 mod，並將範例貼入其中。此 mod 會新增一個 `/gallery` 命令，開啟一個窗格並在其中繪製範例。[窗格](https://code.claude.com/docs/zh-TW/plugins/mods/interface.md#pick-where-to-draw)在寬版全螢幕終端機中是逐字稿旁的側邊欄，否則則是提示詞上方的框線區域。

**1. 建立 mod**

建立一個名為 `gallery` 的目錄，並在其中建立 `.claude-plugin` 和 `hooks` 目錄。[建立 mod](https://code.claude.com/docs/zh-TW/plugins/mods/create.md#write-a-mod-yourself) 說明了這些檔案。

將 manifest 儲存為 `gallery/.claude-plugin/plugin.json`：

```json gallery/.claude-plugin/plugin.json theme={null}
{
  "name": "gallery",
  "version": "0.1.0",
  "description": "Opens a pane that draws one sample",
  "author": { "name": "Your Name" }
}
```

在 `gallery/hooks/hooks.json` 中指定您的進入點：

```json gallery/hooks/hooks.json theme={null}
{
  "modules": ["./register.js"]
}
```

將程式碼儲存為 `gallery/hooks/register.js`。它會新增一個開啟窗格的 `/gallery` 命令，並在該窗格中繪製 `Plain text`：

```javascript gallery/hooks/register.js theme={null}
// Stands in for your own callback in the samples that take one
const noop = () => {}
// The Select sample keeps its choice here
let picked = 'md'

// The Raster sample packs its cells with this function
const DEFAULT_COLOR = 0x01000000
function cellsOf(rows) {
  const numbers = rows.flat().flatMap(([char, color]) => [char.codePointAt(0), color, DEFAULT_COLOR])
  return new Uint8Array(Uint32Array.from(numbers).buffer).toBase64()
}

export function register(on) {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'gallery', description: 'Open the sample pane' })
    return next(e)
  })

  on('command.run', { command: 'gallery' }, async ($) => {
    await $.ui.open({ id: 'gallery', focus: true, closeOnEscape: true })
    return {}
  })

  on('ui.render', { component: 'Pane' }, async ($, e, next) => {
    if (e.requestId !== 'gallery') return next(e)
    const { Box, Text, Button, Input, Select, Link, Markdown, Code, Raster, Svg } = $.ui.resolve(e)
    // Replace the element after return with a sample
    return Text({ children: ['Plain text'] })
  })
}
```

**2. 執行 mod**

在您的 shell 中，從包含 `gallery` 的目錄啟動 Claude Code：

```bash theme={null}
claude --plugin-dir ./gallery
```

在 Claude Code 提示字元中，執行 `/gallery`。會開啟一個顯示 `Plain text` 的窗格。

**3. 換入範例**

從本頁複製一個範例。在 `register.js` 中，將其貼上以取代 `Text({ children: ['Plain text'] })`，使其接在 `return` 之後，然後儲存檔案。每次儲存時 Claude Code 都會重新載入模組，因此再次執行 `/gallery` 即可查看新範例。

## 挑選元素

範例依您想在螢幕上呈現的內容分組：

* **[顯示文字](#show-text)**：`Text`、`Markdown` 和 `Link`
* **[顯示程式碼與變更](#show-code-and-changes)**：`Code`
* **[排列元素](#arrange-elements)**：`Box`
* **[接收輸入](#take-input)**：`Button`、`Input` 和 `Select`
* **[繪製圖片](#draw-pictures)**：`Raster`、`Svg`、`Image` 和 `Client`

## 顯示文字

有三個元素可將文字呈現在螢幕上：`Text` 用於套用您自己的樣式，`Markdown` 用於已格式化的內容，`Link` 則用於 URL。

### `Text`

`Text` 會以您指定的樣式繪製字串。此範例顯示純文字與八種樣式，每行一種：

```javascript theme={null}
Box({
  flexDirection: 'column',
  children: [
    Text({ children: ['Plain text'] }),
    Text({ bold: true, children: ['bold'] }),
    Text({ italic: true, children: ['italic'] }),
    Text({ underline: true, children: ['underline'] }),
    Text({ strikethrough: true, children: ['strikethrough'] }),
    Text({ dimColor: true, children: ['dimColor'] }),
    Text({ inverse: true, children: ['inverse'] }),
    Text({ color: 'red', children: ["color: 'red'"] }),
    Text({ backgroundColor: 'blue', children: ["backgroundColor: 'blue'"] }),
  ],
})
```

![一個包含九行文字的窗格，每行以其樣式命名：plain、bold、italic、underline、strikethrough、灰色的 dimColor、inverse、color red 以及 backgroundColor blue。](https://mintcdn.com/claude-code/EXkwf0kKMewZsyod/images/mods-el-text-light.png?fit=max\&auto=format\&n=EXkwf0kKMewZsyod\&q=85\&s=90724ce3953d9347b61b6a9266fda451)

`dimColor` 會以灰色繪製文字。`backgroundColor` 只會填滿與文字等寬的範圍。

### `Markdown`

`Markdown` 會以 Claude 回覆的格式來格式化文字。請將內容傳入 `text`，而非 `children`：

```javascript theme={null}
Markdown({
  text: '## Release notes\n\nThis build has **two** fixes and one `flag`:\n\n- Faster start\n- Fewer prompts\n\n> Quoted text',
})
```

![一個窗格，包含粗體標題 Release notes，接著是一個含有一個粗體字和一個彩色程式碼字的句子、一個兩項的清單，以及一段以斜體繪製且左側有直線的引文。](https://mintcdn.com/claude-code/EXkwf0kKMewZsyod/images/mods-el-markdown-light.png?fit=max\&auto=format\&n=EXkwf0kKMewZsyod\&q=85\&s=e40eacc4e3fbe06eb003f4463f552ec1)

標題會以粗體繪製，不含其 `#` 符號。行內程式碼會以彩色繪製，不含其反引號。引文會以斜體繪製，左側有一條直線。

### `Link`

`Link` 會繪製一個標籤，後面接著其 URL：

```javascript theme={null}
Link({ href: 'https://code.claude.com/docs', label: 'Claude Code docs' })
```

![一個只有一行的窗格：標籤 Claude Code docs，接著是灰色的 URL。](https://mintcdn.com/claude-code/EXkwf0kKMewZsyod/images/mods-el-link-light.png?fit=max\&auto=format\&n=EXkwf0kKMewZsyod\&q=85\&s=8217bd2dfb561a8ba57023c6d89ea977)

終端機會在標籤之後以文字形式繪製 URL。點擊是否會開啟它取決於使用者的終端機。

## 顯示程式碼與變更

`Code` 會以 Claude Code 本身的語法色彩繪製原始碼文字，或繪製差異。在 VS Code 擴充功能中，`Code` 會以純文字顯示其 `source`，不會有這些螢幕截圖中的色彩、行號或差異底色。

### `Code`

指定 `language`，或傳入 `path` 讓 Claude Code 據以推斷語言。使用 `startLine` 時，各行會從該數字開始編號：

```javascript theme={null}
Code({
  language: 'javascript',
  startLine: 1,
  source: "const name = 'mods'\nconsole.log('hello ' + name)",
})
```

![一個窗格，包含兩行以語法色彩顯示且帶有行號的 JavaScript。](https://mintcdn.com/claude-code/EXkwf0kKMewZsyod/images/mods-el-code-light.png?fit=max\&auto=format\&n=EXkwf0kKMewZsyod\&q=85\&s=4e13f5d506d3fdcc59d6d9524f48d2a9)

色彩來自使用者的佈景主題。

### 以 `Code` 顯示差異

使用 `format: 'diff'` 時，`source` 是一個或多個 unified diff 區塊：

```javascript theme={null}
Code({
  format: 'diff',
  source: '@@ -1,3 +1,3 @@\n # Mods\n-A mod is a plugin.\n+A mod is a plugin that runs code.\n Read on.',
})
```

![一個包含四行差異的窗格。移除的行以紅色底色顯示，新增的行以綠色底色顯示，各自附有行號。在新增的行中，that runs code 這幾個字的底色較深。](https://mintcdn.com/claude-code/EXkwf0kKMewZsyod/images/mods-el-diff-light.png?fit=max\&auto=format\&n=EXkwf0kKMewZsyod\&q=85\&s=4f12c9f7229ceccd9b4f47479a7235dd)

Claude Code 會繪製行號來取代 `@@` 行。當移除的行與新增的行相似時，有變更的字詞會以較深的底色顯示。

## 排列元素

### `Box`

`Box` 會將其內部的內容以列或欄的方式排列，並可繪製邊框。此範例在一個有邊框的方塊上方放置一列文字：

```javascript theme={null}
Box({
  flexDirection: 'column',
  gap: 1,
  children: [
    Box({
      flexDirection: 'row',
      columnGap: 4,
      children: [Text({ children: ['a row'] }), Text({ children: ['of three'] }), Text({ children: ['items'] })],
    }),
    Box({
      borderStyle: 'round',
      paddingX: 1,
      children: [Text({ children: ["borderStyle: 'round'"] })],
    }),
  ],
})
```

![一個窗格，包含排成一列、彼此相隔四欄的三個字詞，接著是一列空白，然後是圍繞一行文字的圓角邊框。邊框延伸至窗格的完整寬度。](https://mintcdn.com/claude-code/EXkwf0kKMewZsyod/images/mods-el-box-light.png?fit=max\&auto=format\&n=EXkwf0kKMewZsyod\&q=85\&s=cb9263bb02f5c8afb6e5b8450e0cdadc)

邊框會延伸至窗格的寬度。

## 接收輸入

`Button`、`Input` 和 `Select` 是控制項：使用者以 Tab 在它們之間移動，並使用取得焦點的那一個。[鍵盤焦點與快速鍵](https://code.claude.com/docs/zh-TW/plugins/mods/interface.md#know-which-keys-your-mod-can-receive)說明了哪些按鍵會傳送到它們。

以 `focus: true` 開啟窗格，即可為窗格請求鍵盤焦點。輸入的字母會在 `Input` 取得焦點後傳送給它。若要選擇窗格開啟時由哪個欄位取得焦點，請參閱[設定快速鍵與第一個焦點](https://code.claude.com/docs/zh-TW/plugins/mods/interface.md#set-a-hotkey-and-the-first-focus)。

### `Button`

按鈕會執行 `onPress`。此範例顯示預設形式、帶有快速鍵的 `plain` 按鈕，以及一個暗淡的按鈕：

```javascript theme={null}
Box({
  flexDirection: 'column',
  children: [
    Button({ key: 'save', label: 'Save', onPress: noop }),
    Button({ key: 'next', label: 'Next', hotkey: 'n', plain: true, onPress: noop }),
    Button({ key: 'skip', label: 'Skip', dimColor: true, onPress: noop }),
  ],
})
```

![一個窗格，包含三個按鈕，每行一個：以方括號括住的 Save、沒有方括號且 n 為彩色的 n: Next，以及以方括號括住的灰色 Skip。](https://mintcdn.com/claude-code/EXkwf0kKMewZsyod/images/mods-el-button-light.png?fit=max\&auto=format\&n=EXkwf0kKMewZsyod\&q=85\&s=8c638c15e12d9736f327dfcaa797b512)

取得焦點的按鈕會以反白顯示繪製。此處使用者已按了兩次 Tab：

![相同的三個按鈕，其中第二個按鈕 n: Next 以反白顯示繪製。](https://mintcdn.com/claude-code/EXkwf0kKMewZsyod/images/mods-el-button-plain-focused-light.png?fit=max\&auto=format\&n=EXkwf0kKMewZsyod\&q=85\&s=a6224e58d10752a894615047d9824ad9)

### `Input`

`Input` 是文字欄位，預設只容納一行，並會在使用者按下 Enter 時執行 `onSubmit`：

```javascript theme={null}
Input({
  key: 'title',
  label: 'Title',
  placeholder: 'Type a title and press Enter',
  value: '',
  submitLabel: 'save',
  onSubmit: noop,
})
```

未取得焦點時，欄位會顯示其標籤和預留位置文字：

![一個只有一行的窗格：標籤 Title，接著是灰色的預留位置文字 Type a title and press Enter。](https://mintcdn.com/claude-code/EXkwf0kKMewZsyod/images/mods-el-input-light.png?fit=max\&auto=format\&n=EXkwf0kKMewZsyod\&q=85\&s=7d580be1aaf5507032e1962b9167d725)

取得焦點時，標籤會變為粗體，出現游標，並在 `⏎` 之後顯示 `submitLabel`：

![相同的欄位，其標籤為粗體，預留位置文字的第一個字母上有一個區塊游標，以及一個換行符號後接 save 一字。](https://mintcdn.com/claude-code/EXkwf0kKMewZsyod/images/mods-el-input-focused-light.png?fit=max\&auto=format\&n=EXkwf0kKMewZsyod\&q=85\&s=dcfcce0174480cc624d06c8521734fe7)

輸入文字會取代預留位置文字：

![相同的欄位，內含輸入的字母 Rel，後接換行符號和 save 一字。](https://mintcdn.com/claude-code/EXkwf0kKMewZsyod/images/mods-el-input-typed-light.png?fit=max\&auto=format\&n=EXkwf0kKMewZsyod\&q=85\&s=4eb6d4443763a21415dad4e426bc747a)

若需要可容納多行的欄位（例如備註或提交訊息），請將 `rows` 設為 2 或以上：

```javascript theme={null}
Input({
  key: 'note',
  label: 'Note',
  placeholder: 'Write a note',
  rows: 4,
  onSubmit: noop,
})
```

終端機和 Desktop 應用程式會繪製多列。在 VS Code 擴充功能中，欄位只容納一行。`rows` 需要 Claude Code v2.1.301 或更新版本。在較早的版本中，欄位只容納一行。

即使欄位是空的，它也會佔用您設定的列數，最多不超過繪製它的窗格或區帶的高度。欄位取得焦點時，較長的文字會在欄位內捲動。

* 在終端機中，Enter 仍然會提交。在終端機中，使用者可以輸入反斜線後按下 Enter 來開始新的一行，或在[終端機模擬器支援](https://code.claude.com/docs/zh-TW/terminal-config.md#enter-multiline-prompts)的情況下按下 Shift+Enter。這些按鍵與提示詞輸入中使用的相同。
* 在終端機中，Up 和 Down 會在欄位的各列之間移動。從第一列和最後一列，它們會移動到前一個或後一個控制項。
* `onSubmit` 和 `onInput` 會收到完整的文字，其各行以 `\n` 連接。

### `Select`

`Select` 讓使用者從數個選項中挑選一個，並以該選項的 `value` 執行 `onSelect`：

```javascript theme={null}
Select({
  key: 'format',
  label: 'Format',
  value: picked,
  options: [
    { value: 'md', label: 'Markdown' },
    { value: 'html', label: 'HTML' },
    { value: 'txt', label: 'Plain text' },
  ],
  onSelect: (value) => {
    picked = value
  },
})
```

關閉時，它會顯示其標籤和目前的選項：

![一個只有一行的窗格：標籤 Format、目前的選項 Markdown，以及一個小的向下箭頭。](https://mintcdn.com/claude-code/EXkwf0kKMewZsyod/images/mods-el-select-light.png?fit=max\&auto=format\&n=EXkwf0kKMewZsyod\&q=85\&s=4e3b18268ffd87d2cad06442e6d661a9)

開啟時，它會列出其選項並標示其中一個：

![已開啟的選擇器，其三個選項列在標籤下方。第二個選項 HTML 以反白顯示繪製。](https://mintcdn.com/claude-code/EXkwf0kKMewZsyod/images/mods-el-select-moved-light.png?fit=max\&auto=format\&n=EXkwf0kKMewZsyod\&q=85\&s=deb6ce0a49d213235feedaa79ac658c0)

使用者挑選選項後，清單會關閉：

![再次關閉的選擇器，現在顯示 HTML 為目前的選項。](https://mintcdn.com/claude-code/EXkwf0kKMewZsyod/images/mods-el-select-picked-light.png?fit=max\&auto=format\&n=EXkwf0kKMewZsyod\&q=85\&s=f065ab5bc479868f03088dc736f17097)

## 繪製圖片

### `Raster`

`Raster` 是由彩色字元儲存格組成的網格，可用於熱度圖、迷你走勢圖或遊戲棋盤。由終端機負責繪製。此範例使用起始模組中的 `cellsOf` 函式，將儲存格打包成 `Raster` 接受的字串。[繪製彩色儲存格網格](https://code.claude.com/docs/zh-TW/plugins/mods/interface.md#draw-a-grid-of-colored-cells)對此有所說明：

```javascript theme={null}
Raster({
  key: 'grid',
  columns: 3,
  rows: 2,
  cells: cellsOf([
    [['█', 0x2e7d32], ['█', 0xf9a825], ['█', 0xc62828]],
    [['█', 0x2e7d32], ['█', 0x2e7d32], ['█', 0xf9a825]],
  ]),
})
```

![一個窗格，包含由彩色方塊組成的小網格，共兩列、每列三個：綠色、琥珀色和紅色，接著是綠色、綠色和琥珀色。](https://mintcdn.com/claude-code/EXkwf0kKMewZsyod/images/mods-el-raster-light.png?fit=max\&auto=format\&n=EXkwf0kKMewZsyod\&q=85\&s=5ed719481d3dd45b568bab696e57bf16)

`Raster` 會將每個色彩近似為較小調色盤中的顏色，因此 `0x2e7d32` 會繪製為 `#337733`。

### `Svg`

`Svg` 會在 Desktop 應用程式和 VS Code 擴充功能中繪製 SVG 文件：

```javascript theme={null}
Svg({
  alt: 'Three bars of rising height',
  width: 120,
  height: 60,
  source:
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 60"><rect x="10" y="40" width="20" height="20" fill="#2e7d32"/><rect x="50" y="25" width="20" height="35" fill="#f9a825"/><rect x="90" y="5" width="20" height="55" fill="#c62828"/></svg>',
})
```

在終端機中，只回傳 `Svg` 的窗格會以空白狀態開啟。若要在該處繪製其他內容，請檢查 [`e.surface`](https://code.claude.com/docs/zh-TW/plugins/mods/interface#pick-where-to-draw) 並回傳不同的樹狀結構。

### `Image` 和 `Client`

另有兩個元素在此沒有範例。`Image` 會在終端機中繪製 PNG 或原始像素。`Client` 是由您的第二個檔案負責繪製的區域，用於動畫和指標輸入。[元素參考](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#elements)列出了它們的 props。

`Image` 會在下列終端機中繪製為圖片：

* kitty 0.28 或更新版本
* Ghostty
* iTerm2 3.5 或更新版本。在 iTerm2 中繪製需要 Claude Code v2.1.305 或更新版本。

在其他任何終端機中，使用者看到的會是 `Image` 的 `alt` 文字（以暗色顯示），而非圖片。請撰寫能獨立表達意思的 `alt` 文字，因為在下列等情況下也會顯示此文字：

* **GNU screen**：在 screen 內執行的工作階段，無論使用哪種終端機。
* **tmux**：在 tmux 內執行、但未符合[在 tmux 內繪製的需求](#draw-an-image-inside-tmux)的工作階段。
* **背景工作階段**：每個[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)，無論是從哪個終端機附加的。
* **iTerm2 未使用全螢幕渲染時**：在 iTerm2 中，圖片僅在[全螢幕渲染](https://code.claude.com/docs/zh-TW/fullscreen.md)下繪製，且 [`CLAUDE_CODE_ALT_SCREEN_FULL_REPAINT`](https://code.claude.com/docs/zh-TW/env-vars) 設為 `1` 時不會繪製。若要看到圖片，請在 Claude Code 提示字元執行 `/tui fullscreen`，並保持該變數未設定。
* **iTerm2 或 tmux 中以檔案路徑作為來源**：在 iTerm2 中及 tmux 內，`source` 指定 `file` 的 `Image` 會顯示 `alt` 文字，而非圖片。如果您的 mod 有 iTerm2 或 tmux 使用者，請將圖片以 base64 形式放在 `source.png` 或 `source.rgba` 中傳遞，而非以路徑形式放在 `source.file` 中。

如果您的 mod 使用者在能以 Unicode 預留位置字元繪製 kitty 圖形協定影像的終端機中看到暗色文字，可以將 [`CLAUDE_CODE_FORCE_TERMINAL_IMAGES`](https://code.claude.com/docs/zh-TW/env-vars) 設為 `1`。他們不應在 GNU screen 內、3.3 之前版本的 tmux 內、tmux 彈出視窗中，或 tmux 的 `allow-passthrough` 關閉時設定此變數。在這些情況下，他們看不到圖片，且 `alt` 文字的位置會改為顯示一個方框。

#### 在 tmux 內繪製 `Image`

如果 `Image` 在 tmux 內顯示其 `alt` 文字，請檢查下列需求，並一併檢查背景工作階段等[其他 `alt` 文字情況](#image-and-client)：

* Claude Code v2.1.310 或更新版本
* tmux 3.3 或更新版本
* Claude Code 在 tmux 窗格中執行，而非 tmux 彈出視窗
* tmux 在 kitty 0.28 或更新版本、Ghostty 或 iTerm2 3.5 或更新版本中執行
* tmux 選項 `focus-events` 和 `allow-passthrough` 設為 `on`。在 kitty 或 Ghostty 中，`allow-passthrough` 也可以設為 `all`。
* 在 iTerm2 中，tmux [不使用 `-CC`](https://code.claude.com/docs/zh-TW/fullscreen#use-with-tmux) 執行、[全螢幕渲染](https://code.claude.com/docs/zh-TW/fullscreen.md)已開啟，且 `CLAUDE_CODE_ALT_SCREEN_FULL_REPAINT` 未設定。
* 在 iTerm2 中，tmux 視窗不大於 iTerm2 視窗。若要檢查，請在該 tmux 視窗中執行 `tmux display-message -p '#{window_bigger}'`。如果輸出 `1`，請調整 tmux 視窗使其符合大小，然後重新啟動 Claude Code。
* mod 的作者以 `png` 或 `rgba` 位元組傳遞圖片，而非以 `file` 路徑傳遞。如果您使用的是非您撰寫的 mod，且其他需求皆已符合，請請其作者檢查這一項。

對於每個尚未依需求設定的 tmux 選項，請在您的 shell 中執行其命令：

```bash theme={null}
tmux set -g allow-passthrough on
tmux set -g focus-events on
```

接著從 tmux 中斷連結、重新附加，並重新啟動 Claude Code。每當您從不同的終端機附加 tmux 時，都要再次重新啟動。若要在 tmux 伺服器重新啟動後保留這兩個選項，也請[將這兩行加入 `~/.tmux.conf`](https://code.claude.com/docs/zh-TW/terminal-config#configure-tmux)。

## 了解 mod 可以繪製的位置

這些範例都在窗格中繪製。Mod 也可以在其他位置繪製，並呼叫 Claude Code 替它顯示內容：

* **窗格與橫帶**：[挑選繪製位置](https://code.claude.com/docs/zh-TW/plugins/mods/interface.md#pick-where-to-draw)
* **Claude Code 本身的列，例如 spinner**：[變更 Claude Code 既有的繪製內容](https://code.claude.com/docs/zh-TW/plugins/mods/interface.md#change-what-claude-code-already-draws)
* **Toast、狀態列與日誌行**：[在不開始回合的情況下顯示內容](https://code.claude.com/docs/zh-TW/plugins/mods/api.md#show-something-without-starting-a-turn)
* **問題對話框**：[保留工具呼叫直到使用者做出決定](https://code.claude.com/docs/zh-TW/plugins/mods/events.md#hold-a-tool-call-until-the-user-decides)

## 後續步驟

* [在介面中繪製](https://code.claude.com/docs/zh-TW/plugins/mods/interface.md)：逐步建立一個含有分頁的窗格
* [測試繪製](https://code.claude.com/docs/zh-TW/plugins/mods/test.md#test-a-drawing)：從測試中按下您的按鈕
* [元素參考](https://code.claude.com/docs/zh-TW/plugins/mods/reference.md#elements)：每個元素的主要 props 以及繪製它的應用程式
