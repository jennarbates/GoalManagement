#!/usr/bin/env python3
"""Character anatomy for the Chinese pages: radicals, components, word breakdowns.

Everything is hand-written and offline. Three tables:

  RADICALS  radical -> (pinyin, meaning, tip)
  CHARS     character -> pinyin, meaning, radical, parts, note
  BONUS     words the stories use beyond the HSK 1 list in the workbook
            (mostly other official HSK 1 words, a few names and set phrases)

Notes say "Memory hook" when they are a mnemonic rather than real history.
The radical for each character follows the Make Me a Hanzi data that
hanzi_data/*.json comes from (its radStrokes), so the highlighted strokes on
the writing page match the radical named here.

    python3 hanzi_notes.py check     # every HSK 1 character has an entry
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# ── Radicals ──────────────────────────────────────────────────────────────────

RADICALS = {
    "亻": ("rén", "person", "The squeezed form of 人 used on the left side."),
    "人": ("rén", "person", "A person walking, seen from the side. On top it spreads into a roof shape (今, 会)."),
    "女": ("nǚ", "woman", "A kneeling woman. Shows up in family words and 'she': 妈, 她, 好."),
    "子": ("zǐ", "child", "A baby with arms out and legs wrapped up."),
    "口": ("kǒu", "mouth", "A mouth. On the left of a little grammar word (吗, 呢) it means 'a sound you say'."),
    "囗": ("wéi", "enclosure", "A big box around something: a border or a wall (国, 四, 回). Bigger than 口."),
    "讠": ("yán", "speech", "Short form of 言 'words'. Anything about talking: 说, 读, 请, 谢, 认, 识."),
    "氵": ("shuǐ", "water", "Three drops of water (from 水): liquids, rivers, sinking (没)."),
    "木": ("mù", "tree; wood", "A tree with branches and roots. Wooden things: 校, 杯, 桌."),
    "日": ("rì", "sun; day", "The sun. Time words live here: 时, 明, 昨, 晚, 星."),
    "月": ("yuè", "moon; flesh", "The moon, but on the side or bottom it is often 肉 'meat, body' in disguise (有, 脸)."),
    "心": ("xīn", "heart", "A heart: feelings and thinking (想, 您, 怎). On the left it stands up as 忄."),
    "辶": ("chuò", "walk", "A foot on the move: going, distance (这, 进, 还)."),
    "阝": ("yì · fù", "city (right side) · hill (left side)", "On the RIGHT it comes from 邑 'city' (那, 都). On the LEFT it comes from 阜 'hill' (院)."),
    "宀": ("mián", "roof", "A roof: houses and what's under them (家, 字, 客)."),
    "土": ("tǔ", "earth", "Soil and ground, places (在, 坐)."),
    "彳": ("chì", "step", "A small step: walking, or how something goes (很, 往, 得)."),
    "戈": ("gē", "halberd", "A long dagger-axe weapon (我)."),
    "乙": ("yǐ", "twist", "A twisting stroke; dictionaries file hook-shaped characters here (九, 也, 买)."),
    "丨": ("gǔn", "vertical line", "A single downward stroke (中, 个)."),
    "丿": ("piě", "left-falling stroke", "A sweep down to the left (么)."),
    "一": ("yī", "one", "One line. Dictionaries file many simple characters here (七, 三, 上, 下, 不, 来)."),
    "二": ("èr", "two", "Two lines (五)."),
    "亠": ("tóu", "lid", "A lid or hat on top (京, 六)."),
    "冖": ("mì", "cover", "A cloth cover laid over something (写)."),
    "冂": ("jiōng", "frame", "A frame open at the bottom (再)."),
    "匚": ("fāng", "box", "A box lying open on the right (医)."),
    "匕": ("bǐ", "spoon; person turned around", "A spoon, or a person facing the other way (北)."),
    "厶": ("sī", "private", "A small closed loop (去)."),
    "又": ("yòu", "right hand; again", "A right hand (友, 对). Simplified characters often use 又 as a stand-in for a complicated part (欢, 汉)."),
    "寸": ("cùn", "inch; hand", "A hand with a mark at the wrist pulse: measuring, rules (对, 时)."),
    "小": ("xiǎo", "small", "Small (少)."),
    "山": ("shān", "mountain", "Three peaks (岁)."),
    "巾": ("jīn", "cloth", "A hanging cloth or towel (师, 帽)."),
    "干": ("gān", "shield; dry", "A forked stick or shield (年)."),
    "廾": ("gǒng", "two hands", "Two hands raised together (开)."),
    "夕": ("xī", "evening", "A half moon at dusk (多, 名)."),
    "大": ("dà", "big", "A person with arms stretched wide (天, 太)."),
    "十": ("shí", "ten", "Ten (午)."),
    "八": ("bā", "eight; divide", "Two strokes pulling apart. On top it's often written 丷 (六, 关)."),
    "儿": ("ér", "child; legs", "A pair of legs at the bottom (见, 先)."),
    "几": ("jǐ", "small table", "A low table (几)."),
    "爫": ("zhǎo", "claw; hand", "A hand reaching down from above (爱)."),
    "父": ("fù", "father", "A hand holding a stick or tool: father (爸)."),
    "王": ("yù", "jade", "Looks like 王 'king', but on the left it's 玉 'jade' (现, 玩)."),
    "目": ("mù", "eye", "An eye turned upright (看, 睡)."),
    "糸": ("mì", "silk thread", "A twisted skein of silk: threads, tying (系). On the left it shrinks to 纟."),
    "见": ("jiàn", "see", "An eye on legs (觉)."),
    "走": ("zǒu", "walk; run", "A person swinging their arms above a foot (起)."),
    "灬": ("huǒ", "fire", "Four dots at the bottom are fire (点, 热)."),
    "欠": ("qiàn", "open mouth", "A person with their mouth wide open (欢, 歌)."),
    "生": ("shēng", "grow; life", "A plant sprouting out of the ground."),
    "老": ("lǎo", "old", "An old person with long hair and a cane. On top it shrinks to 耂."),
    "工": ("gōng", "work", "A carpenter's square."),
    "气": ("qì", "air; steam", "Wisps of vapour rising."),
    "门": ("mén", "door", "A double door."),
}

# ── Characters ────────────────────────────────────────────────────────────────
# (pinyin, meaning, radical, [(part, what it does)], note)

CHARS = {
    "你": ("nǐ", "you", "亻", [("亻", "person"), ("尔", "ěr · sound")],
           "The person (亻) you're talking to. 尔 was an old word for 'you' and gives the sound."),
    "好": ("hǎo", "good", "女", [("女", "woman"), ("子", "child")],
           "A woman holding a child: the old picture of 'good'."),
    "我": ("wǒ", "I; me", "戈", [("手", "hand, squeezed"), ("戈", "halberd")],
           "First a drawing of a toothed weapon, borrowed for 'I'. Memory hook: a hand (手) gripping a halberd (戈)."),
    "是": ("shì", "to be; yes", "日", [("日", "sun"), ("正", "correct, squashed")],
           "Memory hook: what's correct (正) under the sun (日) simply 'is'."),
    "不": ("bù", "not; no", "一", [],
           "An old drawing (probably a flower's base) borrowed for 'not'. Becomes bú before a 4th tone: 不是 bú shì."),
    "吗": ("ma", "yes/no question word", "口", [("口", "mouth"), ("马", "mǎ · sound")],
           "Mouth (口) = a spoken little word; horse (马) gives the 'ma'. Add it to the end of a sentence to ask yes or no."),
    "呢": ("ne", "'and…?' question word", "口", [("口", "mouth"), ("尼", "ní · sound")],
           "Another mouth particle. 你呢？ = 'And you?'"),
    "很": ("hěn", "very", "彳", [("彳", "step"), ("艮", "gèn · sound")],
           "The step radical doesn't help with meaning here; 艮 carries the sound (also in 跟 gēn, 根 gēn)."),
    "也": ("yě", "also; too", "乙", [],
           "An old drawing (maybe a snake or a pouring vessel), borrowed for 'also'. It's the right half of 他 and 她."),
    "都": ("dōu", "all; both", "阝", [("者", "zhě · sound"), ("阝", "city, right side")],
           "阝 on the right comes from 邑 'city'. Read dū it still means 'capital': 首都 shǒudū."),
    "在": ("zài", "at; in; to be (somewhere)", "土", [("才", "sprout"), ("土", "earth")],
           "A sprout pushing out of the earth (土): something that is there."),
    "有": ("yǒu", "to have; there is", "月", [("𠂇", "hand"), ("月", "meat")],
           "A hand (the top part) holding a piece of meat (月 here is 肉): to have."),
    "这": ("zhè", "this", "辶", [("文", "wén"), ("辶", "walk")],
           "辶 'walking' is about distance; 这 is the one close by. Traditional 這 had 言 inside; simplified swapped in 文."),
    "那": ("nà", "that", "阝", [("冄", "old form"), ("阝", "city, right side")],
           "First a place name, borrowed for 'that'. Add a mouth 口 and you get 哪 'which?'."),
    "哪": ("nǎ", "which; where", "口", [("口", "mouth"), ("那", "that")],
           "'That' (那) plus a mouth (口) turns it into a question: which one?"),
    "个": ("gè", "general measure word", "丨", [("人", "person"), ("丨", "stick")],
           "A person (人) holding a stick: the all-purpose counter. 一个人, 这个, 那个."),
    "人": ("rén", "person", "人", [],
           "A person walking, seen from the side."),
    "他": ("tā", "he; him", "亻", [("亻", "person"), ("也", "yě")],
           "Person + 也. Same sound as 她 'she' (女) and 它 'it'."),
    "她": ("tā", "she; her", "女", [("女", "woman"), ("也", "yě")],
           "Woman + 也. Only invented around 1920 so writers could tell 'she' from 'he'."),
    "们": ("men", "plural for people", "亻", [("亻", "person"), ("门", "mén · sound")],
           "Person + door (门) for the sound. Turns people into groups: 我们, 你们, 他们."),
    "叫": ("jiào", "to be called; to shout", "口", [("口", "mouth"), ("丩", "jiū · sound")],
           "A mouth calling out. 我叫… = 'I'm called…'."),
    "什": ("shén", "(in 什么)", "亻", [("亻", "person"), ("十", "ten")],
           "First a squad of ten people (亻 + 十). Today you see it almost only in 什么 'what'."),
    "么": ("me", "(word ending)", "丿", [("丿", "slash"), ("厶", "loop")],
           "A grammar helper with no meaning of its own: 什么, 这么, 怎么."),
    "名": ("míng", "name", "口", [("夕", "evening"), ("口", "mouth")],
           "In the dark (夕) nobody can see your face, so you call out (口) your name."),
    "字": ("zì", "character; word", "子", [("宀", "roof"), ("子", "child")],
           "A child (子) under a roof (宀): children at home learning to write."),
    "学": ("xué", "to study; to learn", "子", [("⺍", "hands, simplified"), ("冖", "cover"), ("子", "child")],
           "A child (子) under a roof while knowledge is handed down from above."),
    "生": ("shēng", "to be born; life", "生", [],
           "A plant sprouting from the ground. In people words it means 'person': 学生, 医生, 先生."),
    "老": ("lǎo", "old; respected", "老", [],
           "An old person with long hair leaning on a cane. In 老师 it means respect, not age."),
    "师": ("shī", "teacher; master", "巾", [("丨丿", "from 𠂤, troops"), ("帀", "around")],
           "First an army division, then 'master'. Traditional form: 師."),
    "校": ("xiào", "school", "木", [("木", "wood"), ("交", "jiāo · sound")],
           "Wood (木) + 交 for the sound: first a wooden enclosure, now 'school'."),
    "中": ("zhōng", "middle", "丨", [("口", "box"), ("丨", "line through it")],
           "A line straight through the middle of a box, like a flag pole at the centre of camp."),
    "国": ("guó", "country", "囗", [("囗", "border"), ("玉", "jade")],
           "Treasure (玉) inside a border (囗) = a country. Traditional 國 had 或, a guarded land, inside."),
    "北": ("běi", "north", "匕", [("丬", "a person"), ("匕", "a person turned away")],
           "Two people standing back to back. Chinese houses face south, so your back is to the north. 背 'back' grew from it."),
    "京": ("jīng", "capital city", "亠", [("亠", "roof"), ("口", "tower"), ("小", "base")],
           "A tall tower on a raised base: the grand buildings of a capital. 东京 Tokyo = 'east capital'."),
    "家": ("jiā", "home; family", "宀", [("宀", "roof"), ("豕", "pig")],
           "A pig under a roof: a household with its animals = home."),
    "爸": ("bà", "dad", "父", [("父", "father"), ("巴", "bā · sound")],
           "Father (父) + 巴 for the 'ba' sound."),
    "妈": ("mā", "mom", "女", [("女", "woman"), ("马", "mǎ · sound")],
           "Woman (女) + horse (马) for the sound. Same trick as 吗."),
    "儿": ("ér", "child; son; -r ending", "儿", [],
           "A small child (simplified from 兒). Also the -r ending in 哪儿, 这儿, 一点儿."),
    "子": ("zǐ", "child; (noun ending zi)", "子", [],
           "A baby with arms out. Said lightly as 'zi' it ends nouns: 儿子, 桌子."),
    "女": ("nǚ", "woman; female", "女", [],
           "A kneeling woman with crossed arms."),
    "朋": ("péng", "friend", "月", [("月", ""), ("月", "")],
           "Two of the same thing side by side (first strings of shells, now two 月): equals, companions."),
    "友": ("yǒu", "friend", "又", [("𠂇", "hand"), ("又", "hand")],
           "Two hands working together: friends."),
    "医": ("yī", "medicine; to heal", "匚", [("匚", "box"), ("矢", "arrow")],
           "Arrows (矢) in a box (匚): treating arrow wounds. Traditional 醫 also had 酉 'wine', used as medicine."),
    "工": ("gōng", "work; labour", "工", [],
           "A carpenter's square."),
    "作": ("zuò", "to do; to make", "亻", [("亻", "person"), ("乍", "zhà · sound")],
           "A person (亻) doing something; 乍 gives the sound."),
    "吃": ("chī", "to eat", "口", [("口", "mouth"), ("乞", "qǐ · sound")],
           "Mouth + 乞 for the sound."),
    "喝": ("hē", "to drink", "口", [("口", "mouth"), ("曷", "hé · sound")],
           "Mouth + 曷 for the sound."),
    "看": ("kàn", "to look; to watch; to read", "目", [("手", "hand"), ("目", "eye")],
           "A hand (手) held over the eye (目), shading it to look into the distance."),
    "听": ("tīng", "to listen", "口", [("口", "mouth"), ("斤", "jīn")],
           "Simplified to mouth + 斤. The traditional form 聽 is packed with meaning: ear 耳, eye, heart 心."),
    "说": ("shuō", "to speak; to say", "讠", [("讠", "speech"), ("兑", "duì · sound")],
           "Speech (讠) + 兑 for the sound."),
    "读": ("dú", "to read (aloud); to study", "讠", [("讠", "speech"), ("卖", "mài")],
           "Speech (讠) + 卖. Memory hook: reading aloud like a seller (卖) calling out their wares."),
    "写": ("xiě", "to write", "冖", [("冖", "cover"), ("与", "yǔ")],
           "Simplified from 寫. Watch the bottom: it's 与, not 马."),
    "会": ("huì", "can (learned skill); meeting", "人", [("人", "people, as a roof"), ("云", "cloud")],
           "People coming together: 开会 'have a meeting'. As a verb it's a skill you learned: 我会说汉语."),
    "喜": ("xǐ", "happy; to like", "口", [("壴", "drum"), ("口", "mouth")],
           "A drum (壴, the top) and a singing mouth (口): celebration. 囍 'double happiness' is two of them, at weddings."),
    "欢": ("huān", "joyful", "欠", [("又", "stand-in"), ("欠", "open mouth")],
           "A wide-open mouth (欠) laughing. 又 stands in for the complicated 雚 of traditional 歡."),
    "爱": ("ài", "to love", "爫", [("爫", "hand"), ("冖", "cover"), ("友", "friend")],
           "Traditional 愛 had 心 'heart' in the middle. Simplified swapped in 友 'friend', so people joke it's love without a heart."),
    "想": ("xiǎng", "to think; to want to; to miss", "心", [("相", "xiāng · sound"), ("心", "heart")],
           "相 (looking at each other) over a heart (心): thinking of someone. Also 'would like to': 我想去."),
    "去": ("qù", "to go", "厶", [("土", "ground"), ("厶", "opening")],
           "A person leaving an opening: going away from here."),
    "来": ("lái", "to come", "一", [],
           "A drawing of a wheat plant, borrowed for 'come'. Traditional 來."),
    "回": ("huí", "to return", "囗", [("囗", "outside"), ("口", "inside")],
           "A box inside a box, like a spiral: going round and coming back."),
    "买": ("mǎi", "to buy", "乙", [("乛", "hook"), ("头", "head")],
           "Simplified from 買 (net 网 + money-shell 贝). Add 十 on top and you get 卖 mài 'to sell'."),
    "开": ("kāi", "to open; to drive", "廾", [("一", "bar"), ("廾", "two hands")],
           "Two hands (廾) lifting the bar (一) off a door. Traditional 開 still has the door 門 around it."),
    "坐": ("zuò", "to sit; to ride (a vehicle)", "土", [("人人", "two people"), ("土", "ground")],
           "Two people (人人) sitting on the ground (土). 坐飞机 'sit plane' = go by plane."),
    "住": ("zhù", "to live (somewhere)", "亻", [("亻", "person"), ("主", "zhǔ · sound")],
           "A person (亻) + 主 'host' for the sound: where a person stays."),
    "睡": ("shuì", "to sleep", "目", [("目", "eye"), ("垂", "chuí · droop")],
           "Eyelids (目) drooping (垂): sleep."),
    "觉": ("jiào", "a sleep (jué: to feel)", "见", [("⺍", "top"), ("冖", "cover"), ("见", "see")],
           "From 覺: waking up and seeing clearly. Read jiào in 睡觉, jué in 觉得 'to feel'."),
    "认": ("rèn", "to recognise", "讠", [("讠", "speech"), ("人", "rén · sound")],
           "Speech + person: saying who someone is."),
    "识": ("shí", "to know", "讠", [("讠", "speech"), ("只", "zhǐ · sound")],
           "Speech (讠) + 只 for the sound: knowledge."),
    "谢": ("xiè", "to thank", "讠", [("讠", "speech"), ("射", "shè · sound")],
           "Speech + 射 'shoot' for the sound: words of thanks."),
    "客": ("kè", "guest", "宀", [("宀", "roof"), ("各", "gè · arriving")],
           "Someone arriving (各, a foot coming in) under your roof (宀): a guest."),
    "气": ("qì", "air; mood; manner", "气", [],
           "Wisps of steam rising. In 客气 it's 'manner': acting like a polite guest."),
    "对": ("duì", "correct; facing", "寸", [("又", "hand"), ("寸", "hand")],
           "Two hands (又, 寸) lining things up: 'correct', 'facing'. 对！ = 'Right!'"),
    "起": ("qǐ", "to rise; to get up", "走", [("走", "walk"), ("己", "jǐ · sound")],
           "Walk (走) + 己 for the sound: getting up and going."),
    "没": ("méi", "not (have); didn't", "氵", [("氵", "water"), ("殳", "simplified")],
           "First meant 'to sink under water' (mò): gone, so 'don't have'. 没有 = don't have."),
    "关": ("guān", "to close; to concern", "八", [("丷", "two strokes"), ("天", "")],
           "Simplified from 關, a bar across a door: to close, to be connected."),
    "系": ("xì", "to tie; system", "糸", [("丿", "hand"), ("糸", "silk")],
           "A hand (丿) and threads (糸) tied together: connection. 关系 = ties, relationship."),
    "再": ("zài", "again", "冂", [],
           "Two layers stacked up: a second time."),
    "见": ("jiàn", "to see; to meet", "见", [("目", "eye, short"), ("儿", "legs")],
           "An eye on legs: someone looking. Traditional 見."),
    "请": ("qǐng", "please; to invite; to treat", "讠", [("讠", "speech"), ("青", "qīng · sound")],
           "Polite words (讠) + 青 for the sound. 我请你 = 'my treat'."),
    "一": ("yī", "one", "一", [],
           "One counting rod. Said yí before a 4th tone (一个 yí gè) and yì before the others (一点儿 yìdiǎnr)."),
    "二": ("èr", "two", "二", [],
           "Two counting rods. Before a measure word use 两 liǎng instead: 两个人."),
    "三": ("sān", "three", "一", [],
           "Three counting rods."),
    "四": ("sì", "four", "囗", [("囗", "box"), ("儿", "breath")],
           "Once four lines; later a borrowed character. Memory hook: a mouth with breath coming out."),
    "五": ("wǔ", "five", "二", [],
           "Once an X between two lines, heaven and earth."),
    "六": ("liù", "six", "八", [("亠", "roof"), ("八", "")],
           "A drawing of a hut, borrowed for 'six'."),
    "七": ("qī", "seven", "一", [],
           "First a cross meaning 'cut', still hiding inside 切 'to cut'."),
    "八": ("bā", "eight", "八", [],
           "Two strokes pulling apart: 'divide' (分 has it on top)."),
    "九": ("jiǔ", "nine", "乙", [],
           "A bent arm, borrowed for 'nine'."),
    "十": ("shí", "ten", "十", [],
           "One rod with a crossbar: ten."),
    "几": ("jǐ", "how many (small numbers)", "几", [],
           "A small table, borrowed for 'how many?'. Expecting a small answer: 你几岁？"),
    "多": ("duō", "many; much", "夕", [("夕", ""), ("夕", "")],
           "Two pieces of meat piled up (they look like two 夕 'evenings'): more and more."),
    "少": ("shǎo", "few; little", "小", [("小", "small"), ("丿", "a stroke taken off")],
           "Small (小) with a bit more cut away: few."),
    "岁": ("suì", "years old", "山", [("山", "mountain"), ("夕", "evening")],
           "Simplified from 歲. Memory hook: mountains (山) and evenings (夕) pile up as you age."),
    "今": ("jīn", "now; this (day, year)", "人", [("人", "lid"), ("㇇", "")],
           "A lid closing over the present moment. 今天 'this day', 今年 'this year'."),
    "天": ("tiān", "sky; day", "大", [("一", "line"), ("大", "big person")],
           "The line (一) above a big person's head (大): the sky. One turn of the sky = a day."),
    "明": ("míng", "bright; next", "日", [("日", "sun"), ("月", "moon")],
           "Sun + moon = bright. 明天 = the next bright day."),
    "昨": ("zuó", "yesterday", "日", [("日", "day"), ("乍", "zhà · sound")],
           "Day (日) + 乍 for the sound."),
    "现": ("xiàn", "to appear; now", "王", [("王", "jade"), ("见", "see")],
           "The gleam of jade (王 = 玉) you can see (见): appear, present."),
    "点": ("diǎn", "dot; o'clock; a little", "灬", [("占", "zhàn · sound"), ("灬", "fire/black")],
           "Simplified from 點 (黑 'black' + 占): a small black dot, then the marks on a clock: o'clock."),
    "时": ("shí", "time; hour", "日", [("日", "sun"), ("寸", "measure")],
           "The sun (日) measured (寸): time. Traditional 時."),
    "候": ("hòu", "to wait; season", "亻", [("亻", "person"), ("丨", ""), ("侯", "hóu · sound")],
           "A person waiting. 时候 = 'time, when': 你什么时候来？"),
    "上": ("shàng", "up; on; previous", "一", [],
           "A mark above a line: up. 上午 = the part of the day before noon."),
    "下": ("xià", "down; under; next", "一", [],
           "A mark below a line: down. 下午 = after noon."),
    "午": ("wǔ", "noon", "十", [],
           "First a pestle; later the name of the 11 am to 1 pm hour: noon."),
    "晚": ("wǎn", "late; evening", "日", [("日", "sun"), ("免", "miǎn · sound")],
           "The sun (日) slipping away (免): late in the day."),
    "月": ("yuè", "moon; month", "月", [],
           "A crescent moon. One moon = one month: 一月 January."),
    "日": ("rì", "sun; day; date", "日", [],
           "The sun with a spot in the middle. In writing dates: 五月八日."),
    "年": ("nián", "year", "干", [],
           "A person carrying grain on their back: one harvest is one year."),
    "星": ("xīng", "star", "日", [("日", "star"), ("生", "shēng · sound")],
           "First three little suns (stars) over 生 for the sound."),
    "期": ("qī", "period of time", "月", [("其", "qí · sound"), ("月", "moon")],
           "A stretch of time counted by the moon (月). 星期 = week."),
}

# ── Words beyond the workbook's HSK 1 list (names, set phrases, more HSK 1) ────
# word -> (pinyin, meaning, breakdown)

BONUS = {
    "的": ("de", "'s; of (possessive)", "我的 my · 你的 your · 爸爸做的菜 the food Dad made"),
    "了": ("le", "(something changed or is done)", "回家了 'went home' · 很晚了 'it's late now'"),
    "小": ("xiǎo", "small; little", ""),
    "大": ("dà", "big", ""),
    "多": ("duō", "many; more", "多 + verb = do more of it: 多喝水"),
    "小月": ("Xiǎoyuè", "Xiaoyue (a name)", "小 little + 月 moon"),
    "大明": ("Dàmíng", "Daming (a name)", "大 big + 明 bright"),
    "马克": ("Mǎkè", "Mark (a name)", "chosen for sound: Mǎ-kè"),
    "王": ("Wáng", "Wang (a surname)", "also means 'king'"),
    "美国": ("Měiguó", "America; the USA", "美 beautiful + 国 country"),
    "哪国人": ("nǎ guó rén", "from which country?", "哪 which + 国 country + 人 person"),
    "高兴": ("gāoxìng", "happy; glad", "高 high + 兴 excited: spirits are high"),
    "茶": ("chá", "tea", "艹 plants on top: tea leaves"),
    "水": ("shuǐ", "water", "a drawing of flowing water"),
    "书": ("shū", "book", ""),
    "汉语": ("Hànyǔ", "Chinese (the language)", "汉 Han (Chinese) + 语 language"),
    "汉字": ("Hànzì", "Chinese characters", "汉 Han (Chinese) + 字 character"),
    "字": ("zì", "character; handwriting", "你的字很好看 = your handwriting is nice"),
    "这儿": ("zhèr", "here", "这 this + 儿: 'this spot'"),
    "哪儿": ("nǎr", "where?", "哪 which + 儿: 'which spot?'"),
    "哪里哪里": ("nǎli nǎli", "oh, not at all (reply to a compliment)", "literally 'where? where?': where is this good thing you see?"),
    "好吃": ("hǎochī", "tasty", "好 good + 吃 eat: good to eat"),
    "好看": ("hǎokàn", "nice-looking", "好 good + 看 look: good to look at"),
    "太": ("tài", "too; so", "太…了 = so…! / too…!"),
    "菜": ("cài", "dish; food; vegetables", "艹 plants on top"),
    "做": ("zuò", "to make; to cook", "做菜 = cook (make dishes)"),
    "米饭": ("mǐfàn", "cooked rice", "米 rice grain + 饭 meal"),
    "吃饭": ("chī fàn", "to eat (a meal)", "吃 eat + 饭 rice: 'eat rice' just means 'eat'"),
    "电影": ("diànyǐng", "movie", "电 electric + 影 shadow: 'electric shadows'"),
    "电视": ("diànshì", "TV", "电 electric + 视 view"),
    "和": ("hé", "and; with", "joins people and things, not sentences: 我和妈妈"),
    "商店": ("shāngdiàn", "shop; store", "商 trade + 店 shop"),
    "水果": ("shuǐguǒ", "fruit", "水 water + 果 fruit: juicy fruit"),
    "本": ("běn", "measure word for books", "一本书 one book"),
    "请问": ("qǐngwèn", "excuse me, may I ask…", "请 please + 问 ask"),
    "钱": ("qián", "money", "钅 metal on the left: coins"),
    "块": ("kuài", "yuan (spoken)", "literally 'a lump, a piece': 十块 = ten yuan"),
    "贵": ("guì", "expensive", "贝 shell-money at the bottom"),
    "进": ("jìn", "to come in; to enter", "请进 = come in"),
    "中午": ("zhōngwǔ", "noon", "中 middle + 午 noon"),
    "饭店": ("fàndiàn", "restaurant; hotel", "饭 meal + 店 shop"),
    "晚": ("wǎn", "late", "很晚了 = it's late"),
    "吧": ("ba", "(suggestion: let's…)", "我们走吧 = let's go"),
    "晚安": ("wǎn'ān", "good night", "晚 evening + 安 peace"),
    "号": ("hào", "day of the month (spoken)", "五月八号 = May 8th"),
    "生日": ("shēngrì", "birthday", "生 born + 日 day"),
    "生日快乐": ("shēngrì kuàilè", "Happy birthday!", "生日 birthday + 快乐 happy"),
    "今年": ("jīnnián", "this year", "今 now + 年 year"),
    "一起": ("yìqǐ", "together", "一 one + 起 rise: 'rise as one'"),
    "飞机": ("fēijī", "airplane", "飞 fly + 机 machine"),
    "天气": ("tiānqì", "weather", "天 sky + 气 air"),
    "冷": ("lěng", "cold", "冫 ice on the left"),
    "天安门": ("Tiān'ānmén", "Tiananmen (Gate of Heavenly Peace)", "天 heaven + 安 peace + 门 gate"),
    "烤鸭": ("kǎoyā", "roast duck", "烤 roast + 鸭 duck. 北京烤鸭 = Peking duck"),
    "怎么了": ("zěnme le", "what's wrong?", "怎么 how + 了 changed: 'how did it get like this?'"),
    "头疼": ("tóuténg", "headache; head hurts", "头 head + 疼 hurt"),
    "好多了": ("hǎo duō le", "much better", "好 good + 多 much + 了 change"),
    "喂": ("wéi", "hello? (on the phone)", "口 mouth on the left: a call"),
    "可以": ("kěyǐ", "can; OK, sure", "可 may + 以 by means of"),
    "一点儿": ("yìdiǎnr", "a little", "一 one + 点 dot + 儿: 'one little dot'"),
    "电话": ("diànhuà", "phone", "电 electric + 话 speech"),
    "见": ("jiàn", "to see; to meet", "time or place + 见 = see you then: 明天见"),
    "那儿": ("nàr", "there; over by", "那 that + 儿: 'that spot'. 学校那儿 = over by the school"),
    "车": ("chē", "car", "a drawing of a cart seen from above. 开车 = drive"),
    "阿姨": ("āyí", "auntie (a friend's mom, any older woman)", "阿 (friendly prefix) + 姨 mother's sister"),
}


# ── Lookups ───────────────────────────────────────────────────────────────────

def is_han(ch: str) -> bool:
    return "一" <= ch <= "鿿" or "㐀" <= ch <= "䶿"


def char_info(ch: str) -> dict | None:
    row = CHARS.get(ch)
    if not row:
        return None
    py, en, rad, parts, note = row
    r = RADICALS.get(rad)
    return {"char": ch, "pinyin": py, "meaning": en, "radical": rad,
            "radical_pinyin": r[0] if r else "", "radical_meaning": r[1] if r else "",
            "radical_tip": r[2] if r else "", "parts": parts, "note": note,
            "is_radical": rad == ch}


def radical_info(rad: str) -> dict | None:
    r = RADICALS.get(rad)
    return {"radical": rad, "pinyin": r[0], "meaning": r[1], "tip": r[2]} if r else None


# Literal readings for multi-character HSK 1 words. Anything missing falls back
# to joining each character's own meaning.
WORD_LITERAL = {
    "你好": "you + good: 'you, well?' = hello",
    "什么": "什 + 么 (a word ending): what",
    "名字": "名 name + 字 characters: the characters of your name",
    "学生": "学 study + 生 person: someone who studies",
    "老师": "老 respected + 师 master: teacher",
    "学校": "学 study + 校 school: a place of study",
    "中国": "中 middle + 国 country: the Middle Kingdom",
    "北京": "北 north + 京 capital: the Northern Capital",
    "爸爸": "爸 dad, said twice like 'papa'",
    "妈妈": "妈 mom, said twice like 'mama'",
    "儿子": "儿 child + 子 child: son",
    "女儿": "女 female + 儿 child: daughter",
    "朋友": "朋 companion + 友 friend: friend",
    "医生": "医 medicine + 生 person: the medicine person",
    "工作": "工 labour + 作 do: work; job",
    "喜欢": "喜 happy + 欢 joyful: to like",
    "睡觉": "睡 sleep + 觉 a sleep: to go to sleep",
    "认识": "认 recognise + 识 know: to know (a person)",
    "谢谢": "谢 thank, said twice: thank you",
    "不客气": "不 don't + 客气 act like a polite guest: 'no need to be polite' = you're welcome",
    "对不起": "对 face + 不 can't + 起 rise to: 'I can't face you' = sorry",
    "没关系": "没 no + 关系 connection: 'it has nothing to do with anything' = no problem",
    "再见": "再 again + 见 see: see you again = goodbye",
    "多少": "多 many + 少 few: 'many or few?' = how many, how much",
    "今天": "今 now + 天 day: today",
    "明天": "明 next (bright) + 天 day: tomorrow",
    "昨天": "昨 past + 天 day: yesterday",
    "现在": "现 now + 在 at: right now",
    "时候": "时 time + 候 period: time; when",
    "上午": "上 before + 午 noon: morning",
    "下午": "下 after + 午 noon: afternoon",
    "晚上": "晚 late + 上 on: evening",
    "星期": "星 star + 期 period: week (named after the 7 'stars': sun, moon and 5 planets)",
    "星期天": "星期 week + 天 day: Sunday (also 星期日)",
}
for _i, _n in enumerate("一二三四五六", 1):
    WORD_LITERAL[f"星期{_n}"] = f"星期 week + {_n} {['one','two','three','four','five','six'][_i-1]}: day {_i} of the week"


def word_breakdown(word: str) -> dict:
    """{'chars': [char_info...], 'literal': str} for any word."""
    chars = [char_info(c) or {"char": c, "pinyin": "", "meaning": "", "radical": "", "parts": [], "note": ""}
             for c in word if is_han(c)]
    literal = WORD_LITERAL.get(word, "")
    if not literal and len(chars) > 1:
        literal = " + ".join(f'{c["char"]} {c["meaning"].split(";")[0]}' for c in chars if c["meaning"])
    return {"chars": chars, "literal": literal}


def same_radical(rad: str, chars) -> list[str]:
    """Characters from `chars` whose radical is `rad`, in order, no repeats."""
    out = []
    for c in chars:
        info = CHARS.get(c)
        if info and info[2] == rad and c not in out:
            out.append(c)
    return out


# ── Segmenting story lines ────────────────────────────────────────────────────

def segment(text: str, vocab: set[str]) -> list[str]:
    """Greedy longest match against the HSK list plus BONUS; non-Han runs pass through."""
    words = vocab | set(BONUS)
    longest = max(len(w) for w in words)
    out, i = [], 0
    while i < len(text):
        if not is_han(text[i]):
            i += 1
            continue
        for n in range(min(longest, len(text) - i), 0, -1):
            if text[i:i + n] in words:
                out.append(text[i:i + n])
                i += n
                break
        else:
            out.append(text[i])  # unknown character
            i += 1
    return out


def _check() -> int:
    sys.path.insert(0, str(HERE / "workbooks"))
    from dailyWorkbookLocal import HSK1_VOCAB
    import json
    missing = sorted({c for w in HSK1_VOCAB for c in w["char"] if is_han(c) and c not in CHARS})
    bad_rad = sorted(c for c, row in CHARS.items() if row[2] not in RADICALS)
    print("missing chars:", "".join(missing) or "none")
    print("radical not in RADICALS:", "".join(bad_rad) or "none")
    # Does the radical's stroke count match the strokes Make Me a Hanzi marks as the radical?
    for c, row in CHARS.items():
        p = HERE / "hanzi_data" / f"{c}.json"
        if p.exists():
            d = json.loads(p.read_text(encoding="utf-8"))
            rs = d.get("radStrokes")
            if rs is None and row[2] != c:
                print(f"  {c}: no radStrokes (radical {row[2]})")
    return 1 if missing or bad_rad else 0


if __name__ == "__main__":
    if sys.argv[1:2] == ["check"]:
        sys.exit(_check())
    print(__doc__)
