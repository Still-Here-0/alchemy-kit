# Neovim Live-Buffer Edit Tool

## Goal

Provide an AI tool that edits the current in-memory Neovim buffer instead of
editing the file on disk. This prevents an AI edit from being based on stale
file contents when the buffer contains unsaved changes.

The tool must:

- target a buffer by number or absolute path;
- reject edits based on stale buffer content;
- show a unified diff before changing the buffer;
- replace a precise line range atomically;
- preserve Neovim undo history;
- return the updated buffer tick, changed lines, and diagnostics;
- never save the buffer implicitly.

## Important integration constraint

Adding Lua code to the Neovim configuration does not automatically make a new
tool available to an AI assistant. The client that sends chat requests must
also register and advertise the tool in its API request, then route tool calls
to Neovim.

There are therefore two components:

1. A Neovim Lua function that safely edits a live buffer.
2. A tool adapter in the chat/plugin integration that exposes that function to
   the assistant as `live_buffer_edit`.

The assistant can use the tool only after the tool appears in the tool list
provided to it. A prompt asking the assistant to use an unregistered tool is
not sufficient.

## Proposed tool contract

Use zero-based, end-exclusive line indexes to match `nvim_buf_set_lines()`.

### Input schema

```json
{
  "type": "object",
  "properties": {
    "buffer": {
      "description": "Neovim buffer number or absolute filename",
      "oneOf": [
        { "type": "integer", "minimum": 1 },
        { "type": "string", "minLength": 1 }
      ]
    },
    "expected_changedtick": {
      "description": "changedtick returned by the latest buffer read",
      "type": "integer",
      "minimum": 0
    },
    "start_line": {
      "description": "Zero-based first line to replace",
      "type": "integer",
      "minimum": 0
    },
    "end_line": {
      "description": "Zero-based exclusive end line",
      "type": "integer",
      "minimum": 0
    },
    "expected_lines": {
      "description": "Exact current lines expected in the replacement range",
      "type": "array",
      "items": { "type": "string" }
    },
    "replacement": {
      "description": "Replacement lines without newline characters",
      "type": "array",
      "items": { "type": "string" }
    }
  },
  "required": [
    "buffer",
    "expected_changedtick",
    "start_line",
    "end_line",
    "expected_lines",
    "replacement"
  ],
  "additionalProperties": false
}
```

`expected_changedtick` prevents an edit after any intervening buffer change.
`expected_lines` provides a second exact-content check and makes failures easy
to explain.

### Result

```json
{
  "buffer": 7,
  "filename": "/absolute/path/to/file.py",
  "changedtick": 155,
  "start_line": 37,
  "end_line": 44,
  "lines": ["updated", "buffer", "lines"],
  "saved": false
}
```

Stale input should return an error and make no change.

## Neovim Lua implementation

Place this module at:

```text
~/.config/nvim/lua/ai_tools/live_buffer_edit.lua
```

```lua
local M = {}

local function resolve_buffer(target)
  if type(target) == "number" then
    if not vim.api.nvim_buf_is_valid(target) then
      error(("invalid buffer: %d"):format(target))
    end
    return target
  end

  if type(target) ~= "string" or target == "" then
    error("buffer must be a buffer number or filename")
  end

  local wanted = vim.fs.normalize(vim.fn.fnamemodify(target, ":p"))
  for _, bufnr in ipairs(vim.api.nvim_list_bufs()) do
    local name = vim.api.nvim_buf_get_name(bufnr)
    if name ~= "" and vim.fs.normalize(vim.fn.fnamemodify(name, ":p")) == wanted then
      return bufnr
    end
  end

  error(("file is not loaded in a buffer: %s"):format(wanted))
end

local function same_lines(actual, expected)
  if #actual ~= #expected then
    return false
  end

  for index, line in ipairs(actual) do
    if line ~= expected[index] then
      return false
    end
  end

  return true
end

function M.apply(args)
  vim.validate({
    args = { args, "table" },
    expected_changedtick = { args.expected_changedtick, "number" },
    start_line = { args.start_line, "number" },
    end_line = { args.end_line, "number" },
    expected_lines = { args.expected_lines, "table" },
    replacement = { args.replacement, "table" },
  })

  local bufnr = resolve_buffer(args.buffer)
  if not vim.bo[bufnr].modifiable then
    error(("buffer is not modifiable: %d"):format(bufnr))
  end

  local line_count = vim.api.nvim_buf_line_count(bufnr)
  if args.start_line < 0 or args.end_line < args.start_line or args.end_line > line_count then
    error("invalid line range")
  end

  local tick = vim.api.nvim_buf_get_changedtick(bufnr)
  if tick ~= args.expected_changedtick then
    error(("stale edit: expected changedtick %d, got %d"):format(
      args.expected_changedtick,
      tick
    ))
  end

  local actual = vim.api.nvim_buf_get_lines(
    bufnr,
    args.start_line,
    args.end_line,
    true
  )
  if not same_lines(actual, args.expected_lines) then
    error("stale edit: current lines do not match expected_lines")
  end

  vim.api.nvim_buf_set_lines(
    bufnr,
    args.start_line,
    args.end_line,
    true,
    args.replacement
  )

  local new_end = args.start_line + #args.replacement
  return {
    buffer = bufnr,
    filename = vim.api.nvim_buf_get_name(bufnr),
    changedtick = vim.api.nvim_buf_get_changedtick(bufnr),
    start_line = args.start_line,
    end_line = new_end,
    lines = vim.api.nvim_buf_get_lines(bufnr, args.start_line, new_end, true),
    saved = false,
  }
end

return M
```

`nvim_buf_set_lines()` creates a normal undoable buffer change. The module does
not call `:write`, so the user retains control over saving.

## Diff preview

The adapter must display a unified diff and require acceptance before calling
`M.apply()`. Generate the preview from `expected_lines` and `replacement`; do
not read the disk file to generate it.

Recommended flow:

1. Read the live buffer and its `changedtick`.
2. Ask the assistant for a line-range replacement.
3. Build and display the diff in a scratch buffer or confirmation window.
4. On acceptance, call `M.apply()` with the original tick and lines.
5. On rejection, return a rejected result without changing the buffer.
6. If `M.apply()` reports a stale edit, re-read the buffer and request a new
   edit. Never retry an old edit automatically.

## Registering the tool with the chat integration

The adapter must advertise a function named `live_buffer_edit` using the JSON
schema above. Its handler should:

1. validate the JSON arguments;
2. render the preview;
3. obtain user acceptance;
4. invoke `require("ai_tools.live_buffer_edit").apply(args)` on Neovim's main
   event loop;
5. return the Lua result as JSON.

The exact registration code depends on the Neovim AI/chat plugin. Locate that
plugin's tool-registration API and connect its handler to `M.apply()`. If the
plugin runs tools outside Neovim, use its RPC bridge to execute the handler in
the active Neovim instance rather than starting another instance.

Do not implement this by invoking `nvim --server ... --remote-expr` from the
assistant. The registered adapter must own all RPC, preview, validation, and
error handling.

## Assistant usage policy

Add these rules to the tool description or assistant instructions:

- Prefer `live_buffer_edit` whenever the target file is loaded in Neovim.
- Read the live buffer immediately before constructing an edit.
- Pass the returned `changedtick` and exact target lines.
- Make one focused replacement per call.
- On a stale-edit error, re-read and rebuild the edit; never blindly retry.
- Use a disk-file edit tool only when the target is not loaded in Neovim.
- Never save the buffer unless the user explicitly requests it.

## Acceptance checklist

- An unsaved buffer can be edited without losing its unsaved changes.
- A changed `changedtick` rejects the edit without partial modification.
- Mismatched `expected_lines` rejects the edit.
- The user sees and can reject the diff before application.
- One `u` command undoes the applied replacement.
- The tool does not write the file automatically.
- The tool returns the new tick and updated lines.
- The assistant receives `live_buffer_edit` in its registered tool list.
