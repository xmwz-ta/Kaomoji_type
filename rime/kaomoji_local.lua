-- Offline, bounded literal retrieval. No network, files, subprocesses or timers.
local data = require("kaomoji_data")
local M = {}
local function contains(text, part) return text:find(part, 1, true) end
local function exact(text, values)
  for _, value in ipairs(values or {}) do if text == value then return true end end
  return false
end
local function negated(prefix)
  for _, suffix in ipairs({"不", "没", "没有", "不是", "不太", "不想", "别", "并不", "不再", "不是很", "并没有"}) do
    if prefix:sub(-#suffix) == suffix then return true end
  end
  return false
end
function M.analyze(text)
  text = text:lower():gsub("！", "!"):gsub("？", "?")
  local plain = text:gsub("[%s!?.,]", ""):gsub("。", ""):gsub("，", "")
  local scores, topics, caps, tags = {}, {}, {}, {}
  local last = 0
  for _, boundary in ipairs({"，", "。", ",", ";", "；", "但是", "不过", "可是", "然而"}) do
    local from = 1
    while true do
      local a,b = text:find(boundary, from, true)
      if not a then break end
      if b < #text then last = math.max(last, b) end
      from = b + 1
    end
  end
  for _, rule in ipairs(data.rules) do
    local position = nil
    if rule.match ~= "exact" or exact(plain, rule.phrases) then
      for _, phrase in ipairs(rule.phrases) do
        local a = contains(text, phrase)
        if a and (not position or a > position) then position = a end
      end
    end
    if position then
      local no = rule.negatable and negated(text:sub(1, position - 1))
      local weight = (no and .13 or 1) * (position <= last and .4 or 1)
      for emotion, value in pairs(rule.emotions) do scores[emotion] = math.max(scores[emotion] or 0, value * weight) end
      if not no and weight >= .5 then
        for _, tag in ipairs(rule.tags or {}) do tags[tag] = true end
        for emotion, cap in pairs(rule.suppress or {}) do caps[emotion] = math.min(caps[emotion] or 1, cap) end
      end
    end
  end
  for _, topic in ipairs(data.topics) do
    local matched = exact(plain, topic.exact)
    local searchable = text
    for _, excluded in ipairs(topic.exclude_phrases or {}) do
      -- Configured exclusions are literal Chinese words; preserve byte offsets.
      searchable = searchable:gsub(excluded, string.rep(" ",#excluded))
    end
    for _, phrase in ipairs(topic.phrases) do
      local a = contains(searchable, phrase)
      if a and not (topic.kind == "action" and negated(text:sub(1,a-1))) then matched = true end
    end
    if matched then topics[topic.id] = true end
  end
  local completions, strongest = {}, 0
  for _, value in pairs(scores) do strongest = math.max(strongest, value) end
  if not next(topics) and strongest < .6 then
    local count = utf8.len(text) or 0
    for length = math.min(12,count),1,-1 do
      do
        local start = utf8.offset(text,count-length+1)
        local records = (data.prefixes or {})[text:sub(start)]
        if records and not negated(text:sub(1,start-1)) then
          for _, record in ipairs(records) do
            completions[#completions+1] = record.phrase
            if record.kind == "topic" then topics[record.id] = true
            else for emotion,value in pairs(record.emotions) do scores[emotion] = math.max(scores[emotion] or 0,value*.75) end end
          end
          break
        end
      end
    end
  end
  if contains(text, "?") then scores.confused = math.max(scores.confused or 0, contains(text,"??") and .9 or .4) end
  if contains(text, "呵呵") then scores.sarcastic = .92; caps.happy = .2 end
  if contains(text, "救命") then
    local danger = false
    for _, phrase in ipairs({"地震","着火","火灾","追杀","溺水","危险","有人跟踪","喘不过气","害怕"}) do if contains(text,phrase) then danger = true end end
    if danger then scores.scared = .96; scores.pleading = .88
    elseif contains(text,"笑") or contains(text,"哈哈") then scores.amused = .95; caps.scared = .05
    else scores.shocked = .7; scores.pleading = .45 end
  end
  for emotion, cap in pairs(caps) do scores[emotion] = math.min(scores[emotion] or 0, cap) end
  local maximum = 0
  for _, value in pairs(scores) do maximum = math.max(maximum, value) end
  if maximum < .18 then scores.neutral = .75 end
  return {emotions=scores, topics=topics, tags=tags, completions=completions}
end
function M.recommend(text, limit)
  limit = math.max(1, math.min(64, limit or 6))
  local analysis, pool = M.analyze(text), {}
  local topical = next(analysis.topics) ~= nil
  for index, entry in ipairs(data.entries) do
    local overlap, emotion, tags = 0, 0, 0
    for _, topic in ipairs(entry.topics or {}) do if analysis.topics[topic] then overlap = overlap + 1 end end
    for _, label in ipairs(entry.emotions) do emotion = math.max(emotion, analysis.emotions[label] or 0) end
    for _, tag in ipairs(entry.tags) do if analysis.tags[tag] then tags = tags + 1 end end
    if (topical and overlap > 0) or (not topical and #(entry.topics or {}) == 0 and emotion >= .25) then
      pool[#pool+1] = {text=entry.text, family=entry.family, score=overlap + emotion*.8 + tags*.04, index=index,
        completion=table.concat(analysis.completions," / ")}
    end
  end
  table.sort(pool, function(a,b) if a.score == b.score then return a.index < b.index end return a.score > b.score end)
  while #pool > math.max(96,limit*3) do pool[#pool] = nil end
  local result, families = {}, {}
  while #pool > 0 and #result < limit do
    local best, score = 1, -100
    for i, row in ipairs(pool) do
      local adjusted = row.score - math.min(.3, (families[row.family] or 0)*.15)
      if adjusted > score then best, score = i, adjusted end
    end
    local row = table.remove(pool,best)
    families[row.family] = (families[row.family] or 0)+1
    result[#result+1] = row
  end
  return result
end
return M
