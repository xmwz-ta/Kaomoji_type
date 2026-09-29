-- Test doubles expose only methods verified in official librime-lua source.
function make_environment(directory, options)
  options = options or {}
  local ctx = { input = "zhongyuchenggongle", properties = {}, ascii = false,
                composing = true, refreshed = 0, committed_text = "终于成功了", segments = {} }
  function ctx:get_property(key) return self.properties[key] or "" end
  function ctx:set_property(key, value) self.properties[key] = value end
  function ctx:get_option(key) return self.ascii end
  function ctx:is_composing() return self.composing end
  function ctx:refresh_non_confirmed_composition() self.refreshed = self.refreshed + 1 end
  function ctx:push_input(input) self.input = input; self.composing = true end
  function ctx:get_selected_candidate() return self.selected end
  function ctx:get_commit_text() return self.committed_text end
  ctx.composition = {}
  function ctx.composition:toSegmentation() return self end
  function ctx.composition:get_segments() return ctx.segments end
  ctx.commit_notifier = {}
  function ctx.commit_notifier:connect(callback)
    ctx.callback = callback
    return { disconnect = function() ctx.callback = nil end }
  end
  local config = {}
  function config:get_string(key) if key == "kaomoji/ipc_dir" then return directory end end
  function config:get_bool(key) return options[key] end
  function config:get_int(key) return options[key] end
  local env = { engine = { context = ctx, schema = { config = config } } }
  return env, ctx
end
function Candidate(kind, start, finish, text, comment)
  return { type = kind, start = start, _end = finish, text = text, comment = comment, preedit = "" }
end
function run_filter(module, env, candidates)
  local result = {}
  yield = function(candidate) result[#result + 1] = candidate end
  local stream = {}
  function stream:iter()
    local index = 0
    return function() index = index + 1; return candidates[index] end
  end
  module.filter.func(stream, env)
  return result
end
function run_translator(module, env)
  local result = {}
  yield = function(candidate) result[#result + 1] = candidate end
  module.translator.func("km", { start = 0, _end = 2 }, env)
  return result
end
function make_key(name)
  return { repr = function() return name end, release = function() return false end,
           ctrl = function() return false end, alt = function() return false end,
           super = function() return false end }
end
