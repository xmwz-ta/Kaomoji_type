-- Immediate offline recommendations; F8 locks the highlighted Chinese candidate.
local local_engine = require("kaomoji_local")
-- Components are loaded as kaomoji.processor / filter / translator in rime.lua.
local M = { processor = {}, filter = {}, translator = {} }
local states, serial = {}, 0

local function suffix_utf8(value, limit)
  local count = utf8.len(value)
  if not count then return "" end
  if count <= limit then return value end
  return value:sub(utf8.offset(value, count - limit + 1))
end

local function state(env)
  local ctx = env.engine.context
  local id = ctx:get_property("kaomoji_session")
  if id == "" or not states[id] then
    serial = serial + 1
    id = tostring(os.time()) .. "-" .. tostring(serial) .. "-" .. tostring(math.random(100000, 999999))
    ctx:set_property("kaomoji_session", id)
    local config = env.engine.schema.config
    states[id] = { id = id, users = 0,
      enabled = config:get_bool("kaomoji/enabled") ~= false,
      append = config:get_bool("kaomoji/append_to_candidate") ~= false,
      insert_after = math.max(1, math.min(6, config:get_int("kaomoji/insert_after") or 3)),
      auto_count = math.max(1, math.min(12, config:get_int("kaomoji/auto_count") or 6)),
      expanded_count = math.max(6, math.min(64, config:get_int("kaomoji/expanded_count") or 36)),
      cache = {}, order = {}, recent = {}, last_commit = "", commit_time = 0 }
  end
  return states[id]
end

local function rows(st, text, context, limit)
  if not st.enabled or #text == 0 or #text > 1536 then return {} end
  limit = limit or st.auto_count
  local key = text .. "\0" .. limit
  if st.cache[key] then return st.cache[key] end
  local result = local_engine.recommend(text, limit)
  st.cache[key] = result
  st.order[#st.order + 1] = key
  if #st.order > 32 then st.cache[table.remove(st.order, 1)] = nil end
  return result
end
local function prepare(first, env)
  local st = state(env)
  local ctx = env.engine.context
  if not st.enabled or ctx:get_option("ascii_mode") or ctx.input == "km" or first.type == "kaomoji" then return {} end
  -- Only already-converted segments before this candidate are read. Querying the
  -- active menu from its own filter can recurse; never call get_commit_text here.
  local prefix = ""
  local segments = ctx.composition:toSegmentation():get_segments()
  for _, seg in ipairs(segments) do
    if seg._end <= first.start and seg.start < seg._end then
      local selected = seg:get_selected_candidate()
      if selected then prefix = prefix .. selected.text end
    end
  end
  local text = st.locked and st.locked.query or (prefix .. first.text)
  -- Do not feed raw Latin pinyin to the classifier.
  if not text:find("[\228-\233][\128-\191][\128-\191]") then return {} end
  st.active_text = text
  local result = rows(st, text, "", st.locked and st.expanded_count or st.auto_count)
  return result
end

local function init(env)
  local ok, st = pcall(state, env)
  if ok then st.users = st.users + 1; env.kaomoji_id = st.id end
end

local function fini(env)
  local st = states[env.kaomoji_id]
  if not st then return end
  st.users = st.users - 1
  if st.users <= 0 then
    states[st.id] = nil
  end
end

M.filter.init, M.filter.fini = init, fini
function M.filter.func(input, env)
  local first, count, result = nil, 0, {}
  local st = states[env.kaomoji_id]
  if st and env.engine.context.input ~= "km" then
    st.faces, st.faces_input = {}, env.engine.context.input
  end
  if st and st.locked and st.locked.raw ~= env.engine.context.input then st.locked = nil end
  local source
  local inserted = false
  local function emit_faces()
    if inserted or not first or not st then return end
    inserted = true
    for _, row in ipairs(result) do
      local text = st.append and (source.text .. " " .. row.text) or row.text
      local comment = row.completion and row.completion ~= "" and ("联想：" .. row.completion) or ("颜文字 · " .. source.text)
      local candidate = Candidate("kaomoji", source.start, source._end, text, comment)
      st.faces[text] = row.text
      candidate.preedit = source.preedit
      yield(candidate)
    end
  end
  for candidate in input:iter() do
    if not first then
      first = candidate
      source = st and st.locked or first
      local ok, prepared = pcall(prepare, first, env)
      if ok then result = prepared end
      if st and st.locked then emit_faces() end
    end
    yield(candidate)
    count = count + 1
    if st and count == st.insert_after then emit_faces() end
  end
  emit_faces()
end

M.translator.init, M.translator.fini = init, fini
function M.translator.func(input, seg, env)
  if input ~= "km" then return end
  local ctx = env.engine.context
  local st = states[env.kaomoji_id]
  if not st or ctx:get_option("ascii_mode") or os.time() - st.commit_time > 30 then return end
  local ok, result = pcall(function()
    local value = rows(st, st.last_commit, "", st.expanded_count)
    return value
  end)
  if ok then
    st.faces, st.faces_input = {}, ctx.input
    for _, row in ipairs(result) do
      local candidate = Candidate("kaomoji", seg.start, seg._end, row.text, "颜文字")
      st.faces[row.text] = row.text
      candidate.quality = 1000
      yield(candidate)
    end
  end
end

function M.processor.init(env)
  init(env)
  local ctx = env.engine.context
  env.kaomoji_connection = ctx.commit_notifier:connect(function(context)
    pcall(function()
      local st = states[env.kaomoji_id]
      if not st or not st.enabled or context:get_option("ascii_mode") then return end
      st.locked = nil
      local selected = context:get_selected_candidate()
      if selected and selected.type == "kaomoji" then
        -- A recommendation's face must not become context for the next analysis.
        st.last_commit, st.commit_time = "", 0
        return
      end
      local text = context:get_commit_text()
      if not text:find("[\228-\233][\128-\191][\128-\191]") then return end
      st.last_commit, st.commit_time = suffix_utf8(text, 160), os.time()
    end)
  end)
end

function M.processor.fini(env)
  if env.kaomoji_connection then env.kaomoji_connection:disconnect() end
  fini(env)
end

function M.processor.func(key, env)
  local ok, value = pcall(function()
    if key:release() or key:ctrl() or key:alt() or key:super() then return 2 end
    local ctx, st = env.engine.context, states[env.kaomoji_id]
    if not st then return 2 end
    if key:repr() == "Shift+F9" then
      st.last_commit, st.commit_time, st.cache, st.order = "", 0, {}, {}
      st.pending_key = nil
      st.locked = nil
      return 1
    end
    if key:repr() == "F9" then
      st.enabled = not st.enabled
      st.locked = nil
      st.last_commit, st.commit_time, st.cache, st.order, st.pending_key = "", 0, {}, {}, nil
      if ctx:is_composing() then ctx:refresh_non_confirmed_composition() end
      return 1
    end
    if not st.enabled or ctx:get_option("ascii_mode") then return 2 end
    if key:repr() == "Shift+Return" then
      local selected = ctx:get_selected_candidate()
      local face = selected and selected.type == "kaomoji" and st.faces_input == ctx.input
        and st.faces and st.faces[selected.text]
      if not face then return 2 end
      -- Use the original face, never split on spaces inside Unicode art.
      ctx:clear()
      st.locked, st.last_commit, st.commit_time, st.faces = nil, "", 0, {}
      env.engine:commit_text(face)
      return 1
    end
    if key:repr() == "Escape" then st.locked = nil end
    if key:repr() == "F8" then
      if ctx:is_composing() then
        local selected = ctx:get_selected_candidate()
        if selected and selected.type ~= "kaomoji" then
          st.locked = {text=selected.text, query=ctx:get_commit_text(), raw=ctx.input,
            start=selected.start, _end=selected._end, preedit=selected.preedit}
        else st.locked = nil end
        ctx:refresh_non_confirmed_composition()
      elseif #st.last_commit > 0 and os.time() - st.commit_time <= 30 then
        ctx:push_input("km")
      else return 2 end
      return 1
    end
    return 2 -- Never intercept Chinese letters, space, numbers, punctuation or Escape.
  end)
  return ok and value or 2
end

return M
