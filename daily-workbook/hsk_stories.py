#!/usr/bin/env python3
"""Short stories and everyday dialogues for the Chinese pages.

Written in everyday Mandarin: the phrases people actually say (你呢？, 认识你很高兴,
请坐, 没关系, 多少钱？, 太好了, 哪里哪里, 明天见…) rather than textbook drills.

Each story or dialogue becomes available once every HSK 1 word in it has been
learned. Words outside the workbook's list must be in hanzi_notes.BONUS; they
print in a "New in this story" box. Pinyin is written word by word with the
tone changes of 不 and 一 marked, the way textbooks do.

    python3 hsk_stories.py check     # every line segments into known words
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hanzi_notes  # noqa: E402

# ── Stories ───────────────────────────────────────────────────────────────────
# lines: (speaker or "", chinese, pinyin, english)

STORIES = [
    {
        "id": "my-family",
        "title": "我的家", "title_en": "My family",
        "lines": [
            ("", "我叫小月，我是学生。", "Wǒ jiào Xiǎoyuè, wǒ shì xuésheng.", "My name is Xiaoyue, and I'm a student."),
            ("", "我家在北京。", "Wǒ jiā zài Běijīng.", "My family lives in Beijing."),
            ("", "我爸爸是医生，他很喜欢他的工作。", "Wǒ bàba shì yīshēng, tā hěn xǐhuan tā de gōngzuò.", "My dad is a doctor. He really likes his job."),
            ("", "我妈妈是老师。", "Wǒ māma shì lǎoshī.", "My mom is a teacher."),
            ("", "她在我的学校工作。", "Tā zài wǒ de xuéxiào gōngzuò.", "She works at my school."),
            ("", "我的朋友大明也在这个学校。", "Wǒ de péngyou Dàmíng yě zài zhège xuéxiào.", "My friend Daming goes to this school too."),
            ("", "大明很爱看书。", "Dàmíng hěn ài kàn shū.", "Daming loves reading."),
            ("", "我们都喜欢我们的学校。", "Wǒmen dōu xǐhuan wǒmen de xuéxiào.", "We all like our school."),
            ("", "你呢？你喜欢你的学校吗？", "Nǐ ne? Nǐ xǐhuan nǐ de xuéxiào ma?", "And you? Do you like your school?"),
        ],
        "questions": ["What is Xiaoyue's dad's job?", "Where does her mom work?", "What does Daming love doing?"],
        "note": ("的 de = 's", "Put 的 between a person and a thing: 我的学校 'my school', 他的工作 'his job'. "
                 "With family and close friends people often drop it: 我爸爸, 我家."),
    },
    {
        "id": "where-from",
        "title": "你是哪国人？", "title_en": "Where are you from?",
        "lines": [
            ("A", "你好！我叫大明。你叫什么名字？", "Nǐ hǎo! Wǒ jiào Dàmíng. Nǐ jiào shénme míngzi?", "Hi! I'm Daming. What's your name?"),
            ("B", "你好！我叫马克。", "Nǐ hǎo! Wǒ jiào Mǎkè.", "Hi! I'm Mark."),
            ("A", "你是哪国人？", "Nǐ shì nǎ guó rén?", "Where are you from?"),
            ("B", "我是美国人。你呢？", "Wǒ shì Měiguó rén. Nǐ ne?", "I'm American. And you?"),
            ("A", "我是中国人，我家在北京。", "Wǒ shì Zhōngguó rén, wǒ jiā zài Běijīng.", "I'm Chinese. My family is in Beijing."),
            ("B", "你是学生吗？", "Nǐ shì xuésheng ma?", "Are you a student?"),
            ("A", "是，我是这个学校的学生。", "Shì, wǒ shì zhège xuéxiào de xuésheng.", "Yes, I'm a student at this school."),
            ("B", "我也是！我在这儿学汉语。", "Wǒ yě shì! Wǒ zài zhèr xué Hànyǔ.", "Me too! I study Chinese here."),
            ("A", "你的汉语很好！", "Nǐ de Hànyǔ hěn hǎo!", "Your Chinese is really good!"),
            ("B", "哪里哪里。", "Nǎli nǎli.", "Oh, not at all."),
        ],
        "questions": ["Where is Mark from?", "What does Mark study here?", "What does Mark say when Daming praises his Chinese?"],
        "note": ("哪里哪里 nǎli nǎli", "The classic polite reply to a compliment. Literally 'where? where?', as in "
                 "'where is this good thing you see?'. Saying 谢谢 is fine too, and younger people often do."),
    },
    {
        "id": "dinner",
        "title": "吃饭了！", "title_en": "Dinner's ready!",
        "lines": [
            ("", "我很爱吃中国菜。", "Wǒ hěn ài chī Zhōngguó cài.", "I love Chinese food."),
            ("", "我爸爸很会做菜。", "Wǒ bàba hěn huì zuò cài.", "My dad is a really good cook."),
            ("", "我妈妈不做菜，她喜欢喝茶。", "Wǒ māma bú zuò cài, tā xǐhuan hē chá.", "My mom doesn't cook. She likes drinking tea."),
            ("", "我们家都爱吃米饭。", "Wǒmen jiā dōu ài chī mǐfàn.", "Our whole family loves rice."),
            ("", "妈妈说：“吃饭了！”", "Māma shuō: “Chī fàn le!”", "Mom says: “Dinner's ready!”"),
            ("", "我说：“来了！”", "Wǒ shuō: “Lái le!”", "I say: “Coming!”"),
            ("", "爸爸做的菜太好吃了！", "Bàba zuò de cài tài hǎochī le!", "Dad's cooking is so good!"),
            ("", "我说：“谢谢爸爸！”", "Wǒ shuō: “Xièxie bàba!”", "I say: “Thanks, Dad!”"),
        ],
        "questions": ["Who cooks in this family?", "What does mom like to drink?", "What does mom call out when dinner is ready?"],
        "note": ("很会 + verb · 太…了", "会 is 'can', so 很会做菜 is 'really can cook' = good at cooking. "
                 "太…了 means 'so…!': 太好吃了 'so tasty!', 太好了 'great!'."),
    },
    {
        "id": "good-friend",
        "title": "我的好朋友", "title_en": "My good friend",
        "lines": [
            ("", "我的朋友叫小月。", "Wǒ de péngyou jiào Xiǎoyuè.", "My friend is called Xiaoyue."),
            ("", "她是医生，她在北京工作。", "Tā shì yīshēng, tā zài Běijīng gōngzuò.", "She's a doctor and works in Beijing."),
            ("", "她爱看书，也爱看电影。", "Tā ài kàn shū, yě ài kàn diànyǐng.", "She loves reading and watching movies."),
            ("", "我喜欢写汉字。", "Wǒ xǐhuan xiě Hànzì.", "I like writing Chinese characters."),
            ("", "小月说：“你的字很好看！”", "Xiǎoyuè shuō: “Nǐ de zì hěn hǎokàn!”", "Xiaoyue says: “Your handwriting is beautiful!”"),
            ("", "我说：“哪里哪里。”", "Wǒ shuō: “Nǎli nǎli.”", "I say: “Oh, not really.”"),
            ("", "她是我很好的朋友。", "Tā shì wǒ hěn hǎo de péngyou.", "She's a really good friend of mine."),
        ],
        "questions": ["What is Xiaoyue's job?", "What two things does she love doing?", "What does the narrator like doing?"],
        "note": ("看 kàn", "看 covers a lot: 看书 'read a book', 看电影 'watch a movie', 看朋友 'visit a friend', 看医生 'see a doctor'."),
    },
    {
        "id": "classroom",
        "title": "老师好！", "title_en": "Good morning, teacher!",
        "lines": [
            ("", "老师说：“你们好！”", "Lǎoshī shuō: “Nǐmen hǎo!”", "The teacher says: “Hello, everyone!”"),
            ("", "学生们说：“老师好！”", "Xuéshengmen shuō: “Lǎoshī hǎo!”", "The students say: “Hello, teacher!”"),
            ("", "老师说：“这个字你们会写吗？”", "Lǎoshī shuō: “Zhège zì nǐmen huì xiě ma?”", "The teacher says: “Can you write this character?”"),
            ("", "大明说：“我会！”", "Dàmíng shuō: “Wǒ huì!”", "Daming says: “I can!”"),
            ("", "小月说：“我不会。”", "Xiǎoyuè shuō: “Wǒ bú huì.”", "Xiaoyue says: “I can't.”"),
            ("", "老师说：“看我写。这是‘家’字。”", "Lǎoshī shuō: “Kàn wǒ xiě. Zhè shì ‘jiā’ zì.”", "The teacher says: “Watch me write. This is the character 家.”"),
            ("", "“这个字读什么？”", "“Zhège zì dú shénme?”", "“How do you read this character?”"),
            ("", "学生们都说：“jiā！”", "Xuéshengmen dōu shuō: “jiā!”", "All the students say: “jiā!”"),
            ("", "老师说：“很好！”", "Lǎoshī shuō: “Hěn hǎo!”", "The teacher says: “Very good!”"),
        ],
        "questions": ["How do the students greet the teacher?", "Who can write the character, and who can't?", "Which character do they learn?"],
        "note": ("老师好！", "Title + 好 is how you greet someone with a title: 老师好, 医生好. "
                 "To answer 'can you?' just repeat the verb: 我会 / 我不会."),
    },
    {
        "id": "shopping",
        "title": "去买东西", "title_en": "Going shopping",
        "lines": [
            ("", "我和妈妈去商店。", "Wǒ hé māma qù shāngdiàn.", "Mom and I go to the store."),
            ("", "妈妈想买水果。", "Māma xiǎng mǎi shuǐguǒ.", "Mom wants to buy fruit."),
            ("", "我想买一本书。", "Wǒ xiǎng mǎi yì běn shū.", "I want to buy a book."),
            ("", "我说：“请问，这本书多少钱？”", "Wǒ shuō: “Qǐngwèn, zhè běn shū duōshao qián?”", "I say: “Excuse me, how much is this book?”"),
            ("", "“三十五块。”", "“Sānshíwǔ kuài.”", "“Thirty-five yuan.”"),
            ("", "我说：“太贵了！”", "Wǒ shuō: “Tài guì le!”", "I say: “That's too expensive!”"),
            ("", "妈妈说：“没关系，我买。”", "Māma shuō: “Méi guānxi, wǒ mǎi.”", "Mom says: “It's okay, I'll buy it.”"),
            ("", "我说：“谢谢妈妈！”", "Wǒ shuō: “Xièxie māma!”", "I say: “Thanks, Mom!”"),
        ],
        "questions": ["Who goes shopping?", "What does Mom want to buy?", "How much is the book?"],
        "note": ("请问 · 多少钱？", "请问 'may I ask' is the polite way to start a question to a stranger. "
                 "多少钱？ 'how much money?' works for anything: 这个多少钱？"),
    },
    {
        "id": "come-over",
        "title": "来我家吧！", "title_en": "Come over!",
        "lines": [
            ("A", "你想来我家吗？", "Nǐ xiǎng lái wǒ jiā ma?", "Do you want to come over to my place?"),
            ("B", "想！你家在哪儿？", "Xiǎng! Nǐ jiā zài nǎr?", "Yes! Where do you live?"),
            ("A", "我住在学校那儿。", "Wǒ zhù zài xuéxiào nàr.", "I live over by the school."),
            ("B", "好的，我开车去。", "Hǎo de, wǒ kāi chē qù.", "Okay, I'll drive over."),
            ("A", "请进！请坐！", "Qǐng jìn! Qǐng zuò!", "Come in! Have a seat!"),
            ("B", "你家很好看！", "Nǐ jiā hěn hǎokàn!", "Your place looks great!"),
            ("A", "谢谢！这是我妈妈。", "Xièxie! Zhè shì wǒ māma.", "Thanks! This is my mom."),
            ("B", "阿姨好！", "Āyí hǎo!", "Hello, auntie!"),
            ("A", "你想喝什么？", "Nǐ xiǎng hē shénme?", "What would you like to drink?"),
            ("B", "我喝水，谢谢。", "Wǒ hē shuǐ, xièxie.", "Water, thanks."),
            ("B", "很晚了，我回家了。谢谢你！", "Hěn wǎn le, wǒ huí jiā le. Xièxie nǐ!", "It's late, I'm heading home. Thank you!"),
            ("A", "不客气！", "Bú kèqi!", "Anytime!"),
        ],
        "questions": ["How does B get to A's place?", "What does B call A's mom?", "What does B drink?"],
        "note": ("阿姨好！", "Call a friend's mom 阿姨 'auntie' and a friend's dad 叔叔 shūshu 'uncle', even though they're not family. "
                 "Greeting = title + 好."),
    },
    {
        "id": "new-neighbour",
        "title": "认识你很高兴", "title_en": "Nice to meet you",
        "lines": [
            ("A", "你好！我叫王小月，我住在这儿。", "Nǐ hǎo! Wǒ jiào Wáng Xiǎoyuè, wǒ zhù zài zhèr.", "Hi! I'm Wang Xiaoyue. I live here."),
            ("B", "你好！我叫马克，我也住在这儿。", "Nǐ hǎo! Wǒ jiào Mǎkè, wǒ yě zhù zài zhèr.", "Hi! I'm Mark. I live here too."),
            ("A", "认识你很高兴！", "Rènshi nǐ hěn gāoxìng!", "Nice to meet you!"),
            ("B", "认识你我也很高兴。", "Rènshi nǐ wǒ yě hěn gāoxìng.", "Nice to meet you too."),
            ("A", "你是哪国人？", "Nǐ shì nǎ guó rén?", "Where are you from?"),
            ("B", "我是美国人，我来中国工作。", "Wǒ shì Měiguó rén, wǒ lái Zhōngguó gōngzuò.", "I'm American. I came to China to work."),
            ("A", "请进，请坐！你喝茶吗？", "Qǐng jìn, qǐng zuò! Nǐ hē chá ma?", "Come in, have a seat! Would you like some tea?"),
            ("B", "好的，谢谢！", "Hǎo de, xièxie!", "Yes please, thanks!"),
            ("A", "不客气。", "Bú kèqi.", "You're welcome."),
        ],
        "questions": ["Where does Mark live?", "Why did Mark come to China?", "What does Wang Xiaoyue offer him?"],
        "note": ("请 + verb", "请 makes any verb a polite invitation: 请进 'come in', 请坐 'have a seat', 请喝茶 'have some tea'."),
    },
    {
        "id": "my-day",
        "title": "我的一天", "title_en": "My day",
        "lines": [
            ("", "我上午八点去工作。", "Wǒ shàngwǔ bā diǎn qù gōngzuò.", "I go to work at 8 a.m."),
            ("", "中午我和朋友去饭店吃饭。", "Zhōngwǔ wǒ hé péngyou qù fàndiàn chī fàn.", "At noon my friend and I eat at a restaurant."),
            ("", "下午五点我回家。", "Xiàwǔ wǔ diǎn wǒ huí jiā.", "At 5 p.m. I go home."),
            ("", "晚上我看电视，也看书。", "Wǎnshang wǒ kàn diànshì, yě kàn shū.", "In the evening I watch TV and read."),
            ("", "十一点了，妈妈说：“很晚了，睡觉吧！”", "Shíyī diǎn le, māma shuō: “Hěn wǎn le, shuìjiào ba!”", "At eleven, Mom says: “It's late, time for bed!”"),
            ("", "我说：“好的，晚安！”", "Wǒ shuō: “Hǎo de, wǎn'ān!”", "I say: “Okay, good night!”"),
        ],
        "questions": ["What time does the narrator go to work?", "Where do they eat at noon?", "What does Mom say at eleven?"],
        "note": ("Time goes first", "Chinese puts the time before the verb: 我 + 八点 + 去工作 'I at 8 go to work'. Never at the end like English."),
    },
    {
        "id": "birthday",
        "title": "生日快乐！", "title_en": "Happy birthday!",
        "lines": [
            ("", "今天是五月八号，星期六。", "Jīntiān shì wǔ yuè bā hào, xīngqīliù.", "Today is Saturday, May 8th."),
            ("", "今天是我的生日！", "Jīntiān shì wǒ de shēngrì!", "Today is my birthday!"),
            ("", "我今年二十岁了。", "Wǒ jīnnián èrshí suì le.", "I'm turning twenty this year."),
            ("", "我的朋友们都来我家。", "Wǒ de péngyoumen dōu lái wǒ jiā.", "All my friends come to my place."),
            ("", "他们说：“生日快乐！”", "Tāmen shuō: “Shēngrì kuàilè!”", "They say: “Happy birthday!”"),
            ("", "我说：“谢谢你们！”", "Wǒ shuō: “Xièxie nǐmen!”", "I say: “Thank you, everyone!”"),
            ("", "我们一起吃饭，喝茶，看电影。", "Wǒmen yìqǐ chī fàn, hē chá, kàn diànyǐng.", "We eat, drink tea and watch a movie together."),
            ("", "晚上十二点，朋友们都回家了。", "Wǎnshang shí'èr diǎn, péngyoumen dōu huí jiā le.", "At midnight, everyone goes home."),
            ("", "今天我很高兴！", "Jīntiān wǒ hěn gāoxìng!", "I'm so happy today!"),
        ],
        "questions": ["What is the date today?", "How old is the narrator turning?", "What do the friends do together?"],
        "note": ("Dates go big to small", "Year, month, day, weekday: 五月八号，星期六. Spoken Chinese says 号 hào for the day; writing uses 日 rì."),
    },
    {
        "id": "beijing-trip",
        "title": "去北京", "title_en": "A trip to Beijing",
        "lines": [
            ("", "我想去北京看我的朋友。", "Wǒ xiǎng qù Běijīng kàn wǒ de péngyou.", "I want to go to Beijing to see my friend."),
            ("", "星期五下午，我坐飞机去北京。", "Xīngqīwǔ xiàwǔ, wǒ zuò fēijī qù Běijīng.", "On Friday afternoon I fly to Beijing."),
            ("", "北京的天气很冷。", "Běijīng de tiānqì hěn lěng.", "The weather in Beijing is cold."),
            ("", "我们去看天安门。", "Wǒmen qù kàn Tiān'ānmén.", "We go to see Tiananmen."),
            ("", "我们也去吃北京烤鸭。", "Wǒmen yě qù chī Běijīng kǎoyā.", "We also go eat Peking duck."),
            ("", "太好吃了！", "Tài hǎochī le!", "It's so delicious!"),
            ("", "星期天晚上，我坐飞机回家。", "Xīngqītiān wǎnshang, wǒ zuò fēijī huí jiā.", "On Sunday evening I fly home."),
            ("", "我很喜欢北京！", "Wǒ hěn xǐhuan Běijīng!", "I really like Beijing!"),
        ],
        "questions": ["Why does the narrator go to Beijing?", "How do they get there?", "What do they eat?"],
        "note": ("坐 + vehicle", "坐 'sit' is how you say 'take' a plane, bus or taxi: 坐飞机 'fly', 坐出租车 'take a taxi'. "
                 "去 + place + verb = go somewhere to do something: 去北京看朋友."),
    },
    {
        "id": "doctor",
        "title": "看医生", "title_en": "Seeing the doctor",
        "lines": [
            ("", "星期一上午，我不想去学校。", "Xīngqīyī shàngwǔ, wǒ bù xiǎng qù xuéxiào.", "Monday morning, I don't want to go to school."),
            ("", "妈妈说：“你怎么了？”", "Māma shuō: “Nǐ zěnme le?”", "Mom says: “What's wrong?”"),
            ("", "我说：“我头疼。”", "Wǒ shuō: “Wǒ tóuténg.”", "I say: “I have a headache.”"),
            ("", "妈妈说：“我们去看医生。”", "Māma shuō: “Wǒmen qù kàn yīshēng.”", "Mom says: “Let's go see the doctor.”"),
            ("", "医生说：“没关系。多喝水，多睡觉。”", "Yīshēng shuō: “Méi guānxi. Duō hē shuǐ, duō shuìjiào.”", "The doctor says: “It's nothing serious. Drink lots of water and sleep more.”"),
            ("", "我说：“谢谢医生！”", "Wǒ shuō: “Xièxie yīshēng!”", "I say: “Thank you, doctor!”"),
            ("", "医生说：“不客气。再见！”", "Yīshēng shuō: “Bú kèqi. Zàijiàn!”", "The doctor says: “You're welcome. Bye!”"),
            ("", "下午我在家睡觉。晚上我好多了！", "Xiàwǔ wǒ zài jiā shuìjiào. Wǎnshang wǒ hǎo duō le!", "In the afternoon I sleep at home. By evening I feel much better!"),
        ],
        "questions": ["What's wrong with the narrator?", "What does the doctor tell them to do?", "How do they feel by evening?"],
        "note": ("你怎么了？", "'What's wrong?' / 'What happened?'. You'll hear it all the time when someone looks upset or unwell."),
    },
    {
        "id": "phone-movie",
        "title": "看电影", "title_en": "Going to the movies",
        "lines": [
            ("A", "喂，小月！", "Wéi, Xiǎoyuè!", "Hello, Xiaoyue?"),
            ("B", "喂，大明，你好！", "Wéi, Dàmíng, nǐ hǎo!", "Hi, Daming!"),
            ("A", "你明天想去看电影吗？", "Nǐ míngtiān xiǎng qù kàn diànyǐng ma?", "Do you want to see a movie tomorrow?"),
            ("B", "好的！几点？", "Hǎo de! Jǐ diǎn?", "Sure! What time?"),
            ("A", "下午三点，可以吗？", "Xiàwǔ sān diǎn, kěyǐ ma?", "Three in the afternoon, is that okay?"),
            ("B", "可以。在哪儿见？", "Kěyǐ. Zài nǎr jiàn?", "Okay. Where should we meet?"),
            ("A", "在学校见。", "Zài xuéxiào jiàn.", "Let's meet at school."),
            ("B", "好，明天见！", "Hǎo, míngtiān jiàn!", "Great, see you tomorrow!"),
            ("A", "再见！", "Zàijiàn!", "Bye!"),
        ],
        "questions": ["What does Daming invite Xiaoyue to do?", "What time do they agree on?", "Where will they meet?"],
        "note": ("…见", "见 'see' after a time or place makes a goodbye: 明天见 'see you tomorrow', 在学校见 'see you at school', 晚上见 'see you tonight'."),
    },
]

# ── Everyday dialogues: short exchanges built around a set phrase ─────────────
# phrases: (chinese, pinyin, english, when to use it)

DIALOGUES = [
    {"id": "and-you", "title": "Hi, and you?",
     "lines": [("A", "你好！", "Nǐ hǎo!", "Hi!"),
               ("B", "你好！你好吗？", "Nǐ hǎo! Nǐ hǎo ma?", "Hi! How are you?"),
               ("A", "我很好，你呢？", "Wǒ hěn hǎo, nǐ ne?", "I'm good. And you?"),
               ("B", "我也很好。", "Wǒ yě hěn hǎo.", "I'm good too.")],
     "phrases": [("你呢？", "nǐ ne?", "And you?", "Bounce any question back without repeating it."),
                 ("我也…", "wǒ yě…", "me too / I also…", "也 goes right before the verb: 我也很好, 我也是.")]},
    {"id": "names", "title": "What's your name?",
     "lines": [("A", "你叫什么名字？", "Nǐ jiào shénme míngzi?", "What's your name?"),
               ("B", "我叫小月。你呢？", "Wǒ jiào Xiǎoyuè. Nǐ ne?", "I'm Xiaoyue. And you?"),
               ("A", "我叫大明。认识你很高兴！", "Wǒ jiào Dàmíng. Rènshi nǐ hěn gāoxìng!", "I'm Daming. Nice to meet you!"),
               ("B", "我也很高兴认识你。", "Wǒ yě hěn gāoxìng rènshi nǐ.", "Nice to meet you too.")],
     "phrases": [("你叫什么名字？", "nǐ jiào shénme míngzi?", "What's your name?", "Answer with 我叫 + name."),
                 ("认识你很高兴", "rènshi nǐ hěn gāoxìng", "Nice to meet you", "Literally 'knowing you, (I'm) very happy'.")]},
    {"id": "nationality", "title": "Where are you from?",
     "lines": [("A", "你是哪国人？", "Nǐ shì nǎ guó rén?", "Where are you from?"),
               ("B", "我是美国人。你呢？", "Wǒ shì Měiguó rén. Nǐ ne?", "I'm American. And you?"),
               ("A", "我是中国人，我家在北京。", "Wǒ shì Zhōngguó rén, wǒ jiā zài Běijīng.", "I'm Chinese. My family is in Beijing."),
               ("B", "我很喜欢北京！", "Wǒ hěn xǐhuan Běijīng!", "I really like Beijing!")],
     "phrases": [("你是哪国人？", "nǐ shì nǎ guó rén?", "Where are you from?", "Literally 'you are which-country person?'. Answer: 我是 + country + 人.")]},
    {"id": "tea", "title": "Have a seat",
     "lines": [("A", "请坐。你喝茶吗？", "Qǐng zuò. Nǐ hē chá ma?", "Have a seat. Would you like tea?"),
               ("B", "不喝，谢谢。我喝水。", "Bù hē, xièxie. Wǒ hē shuǐ.", "No thanks. I'll have water."),
               ("A", "好的。", "Hǎo de.", "Sure."),
               ("B", "谢谢！", "Xièxie!", "Thank you!"),
               ("A", "不客气。", "Bú kèqi.", "You're welcome.")],
     "phrases": [("请坐", "qǐng zuò", "Please sit", "请 + verb is a polite 'please…': 请进, 请喝茶."),
                 ("不客气", "bú kèqi", "You're welcome", "'Don't be so polite.'"),
                 ("好的", "hǎo de", "OK; sure", "The everyday 'okay'.")]},
    {"id": "sorry", "title": "Sorry! No problem.",
     "lines": [("A", "对不起！", "Duìbuqǐ!", "Sorry!"),
               ("B", "没关系。", "Méi guānxi.", "No problem."),
               ("A", "这是你的书吗？", "Zhè shì nǐ de shū ma?", "Is this your book?"),
               ("B", "是，谢谢你！", "Shì, xièxie nǐ!", "Yes, thank you!")],
     "phrases": [("对不起", "duìbuqǐ", "Sorry", "For a real apology, or when you bump into someone."),
                 ("没关系", "méi guānxi", "It's okay", "'No connection': no harm done.")]},
    {"id": "age", "title": "How old?",
     "lines": [("A", "你儿子几岁了？", "Nǐ érzi jǐ suì le?", "How old is your son?"),
               ("B", "他八岁了。你女儿呢？", "Tā bā suì le. Nǐ nǚ'ér ne?", "He's eight. And your daughter?"),
               ("A", "她五岁。", "Tā wǔ suì.", "She's five.")],
     "phrases": [("几岁了？", "jǐ suì le?", "How old (is the child)?", "几 expects a small number, so it's for kids. For adults ask 你多大了？")]},
    {"id": "time", "title": "What time is it?",
     "lines": [("A", "现在几点？", "Xiànzài jǐ diǎn?", "What time is it?"),
               ("B", "三点。", "Sān diǎn.", "Three o'clock."),
               ("A", "电影几点？", "Diànyǐng jǐ diǎn?", "What time is the movie?"),
               ("B", "下午五点。我们四点去吧。", "Xiàwǔ wǔ diǎn. Wǒmen sì diǎn qù ba.", "5 p.m. Let's leave at four."),
               ("A", "好的！", "Hǎo de!", "Okay!")],
     "phrases": [("现在几点？", "xiànzài jǐ diǎn?", "What time is it?", "Answer with number + 点: 三点."),
                 ("…吧", "ba", "let's…", "吧 at the end softens a suggestion.")]},
    {"id": "price", "title": "How much?",
     "lines": [("A", "这个多少钱？", "Zhège duōshao qián?", "How much is this?"),
               ("B", "十块。", "Shí kuài.", "Ten yuan."),
               ("A", "那个呢？", "Nàge ne?", "And that one?"),
               ("B", "那个八块。", "Nàge bā kuài.", "That one's eight."),
               ("A", "我买那个。", "Wǒ mǎi nàge.", "I'll take that one.")],
     "phrases": [("多少钱？", "duōshao qián?", "How much?", "Point and ask: 这个多少钱？"),
                 ("块", "kuài", "yuan", "The spoken word for 元 yuán.")]},
    {"id": "see-you", "title": "See you tomorrow",
     "lines": [("A", "我回家了。", "Wǒ huí jiā le.", "I'm heading home."),
               ("B", "好的，明天见！", "Hǎo de, míngtiān jiàn!", "Okay, see you tomorrow!"),
               ("A", "再见！", "Zàijiàn!", "Bye!")],
     "phrases": [("明天见", "míngtiān jiàn", "See you tomorrow", "Time + 见: 晚上见, 星期一见."),
                 ("我…了", "wǒ… le", "I'm off to…", "了 at the end: 我回家了 'I'm heading home (now)'.")]},
    {"id": "speak-chinese", "title": "Do you speak Chinese?",
     "lines": [("A", "你会说汉语吗？", "Nǐ huì shuō Hànyǔ ma?", "Can you speak Chinese?"),
               ("B", "我会说一点儿。", "Wǒ huì shuō yìdiǎnr.", "I can speak a little."),
               ("A", "很好！你在哪儿学汉语？", "Hěn hǎo! Nǐ zài nǎr xué Hànyǔ?", "Great! Where do you study Chinese?"),
               ("B", "我在家学。", "Wǒ zài jiā xué.", "I study at home.")],
     "phrases": [("一点儿", "yìdiǎnr", "a little", "我会说一点儿 'I speak a little' is the line you'll use most."),
                 ("在 + place + verb", "zài…", "do something somewhere", "The place comes before the verb: 在家学 'study at home'.")]},
    {"id": "where-live", "title": "Where do you live?",
     "lines": [("A", "你住在哪儿？", "Nǐ zhù zài nǎr?", "Where do you live?"),
               ("B", "我住在北京。你呢？", "Wǒ zhù zài Běijīng. Nǐ ne?", "I live in Beijing. You?"),
               ("A", "我也住在北京！", "Wǒ yě zhù zài Běijīng!", "I live in Beijing too!"),
               ("B", "太好了！", "Tài hǎo le!", "Great!")],
     "phrases": [("太好了！", "tài hǎo le!", "Great!", "太…了 = 'so…!'."),
                 ("住在…", "zhù zài…", "live in…", "我住在北京.")]},
    {"id": "want-eat", "title": "What do you feel like?",
     "lines": [("A", "你想吃什么？", "Nǐ xiǎng chī shénme?", "What do you feel like eating?"),
               ("B", "我想吃米饭。你呢？", "Wǒ xiǎng chī mǐfàn. Nǐ ne?", "I'd like rice. You?"),
               ("A", "我也是。", "Wǒ yě shì.", "Same here.")],
     "phrases": [("我想…", "wǒ xiǎng…", "I'd like to…", "想 + verb is the soft 'want': 我想吃, 我想去."),
                 ("我也是", "wǒ yě shì", "Me too", "Agree with anything.")]},
    {"id": "know-him", "title": "Do you know him?",
     "lines": [("A", "你认识他吗？", "Nǐ rènshi tā ma?", "Do you know him?"),
               ("B", "认识，他是我的老师。", "Rènshi, tā shì wǒ de lǎoshī.", "Yes, he's my teacher."),
               ("A", "是吗？", "Shì ma?", "Really?")],
     "phrases": [("是吗？", "shì ma?", "Really?", "Shows surprise or interest."),
                 ("Yes = repeat the verb", "", "", "There's no single word for 'yes': 你认识他吗？→ 认识. 你会吗？→ 会.")]},
    {"id": "weekday", "title": "What day is it?",
     "lines": [("A", "今天星期几？", "Jīntiān xīngqī jǐ?", "What day is it today?"),
               ("B", "今天星期五。", "Jīntiān xīngqīwǔ.", "It's Friday."),
               ("A", "太好了！明天不工作！", "Tài hǎo le! Míngtiān bù gōngzuò!", "Great! No work tomorrow!")],
     "phrases": [("星期几？", "xīngqī jǐ?", "What day?", "Swap the number for 几 to ask. The answer drops right back in: 星期五.")]},
    {"id": "phone", "title": "On the phone",
     "lines": [("A", "喂，你好！", "Wéi, nǐ hǎo!", "Hello?"),
               ("B", "喂，妈妈！我是小月。", "Wéi, māma! Wǒ shì Xiǎoyuè.", "Hi Mom! It's Xiaoyue."),
               ("A", "你在哪儿？", "Nǐ zài nǎr?", "Where are you?"),
               ("B", "我在学校。晚上回家。", "Wǒ zài xuéxiào. Wǎnshang huí jiā.", "I'm at school. I'll be home this evening.")],
     "phrases": [("喂", "wéi", "Hello? (phone)", "Only for answering the phone or calling out to someone."),
                 ("我是…", "wǒ shì…", "It's… (on the phone)", "我是小月 'it's Xiaoyue'.")]},
]


# ── Picking today's story ─────────────────────────────────────────────────────

def _hsk_words(item: dict, vocab: set[str]) -> list[str]:
    seen = []
    for _, cn, _, _ in item["lines"]:
        for w in hanzi_notes.segment(cn, vocab):
            if w in vocab and w not in seen:
                seen.append(w)
    return seen


def bonus_words(item: dict, vocab: set[str]) -> list[str]:
    seen = []
    for _, cn, _, _ in item["lines"]:
        for w in hanzi_notes.segment(cn, vocab):
            if w not in vocab and w in hanzi_notes.BONUS and w not in seen:
                seen.append(w)
    return seen


def pick(bank: list[dict], vocab: set[str], learned: set[str], focus: list[str],
         recent: list[str], date_str: str, keep: str | None = None) -> dict | None:
    """The best story/dialogue that only uses learned HSK words.

    Prefers ones that use today's lesson words (`focus`, new words first),
    skips ones used in the last few days when there's another choice, and
    breaks ties by date so the pick changes from day to day.
    """
    if keep:
        for item in bank:
            if item["id"] == keep:
                return item
    ok = [s for s in bank if set(_hsk_words(s, vocab)) <= learned]
    if not ok:
        return None
    fresh = [s for s in ok if s["id"] not in recent] or ok

    def score(s):
        words = _hsk_words(s, vocab)
        hits = sum(len(focus) - i for i, w in enumerate(focus) if w in words)
        jitter = hashlib.md5(f'{date_str}{s["id"]}'.encode()).hexdigest()
        return (hits, jitter)
    return max(fresh, key=score)


def _check() -> int:
    sys.path.insert(0, str(HERE / "workbooks"))
    from dailyWorkbookLocal import HSK1_VOCAB
    vocab = {w["char"] for w in HSK1_VOCAB}
    order = {w["char"]: i for i, w in enumerate(HSK1_VOCAB)}
    bad = 0
    for kind, bank in (("story", STORIES), ("dialogue", DIALOGUES)):
        for s in bank:
            unknown = sorted({w for _, cn, _, _ in s["lines"] for w in hanzi_notes.segment(cn, vocab)
                              if w not in vocab and w not in hanzi_notes.BONUS})
            words = _hsk_words(s, vocab)
            level = max((order[w] for w in words), default=0) + 1
            print(f"{kind:8} {s['id']:14} unlocks at word {level:3}  bonus: {' '.join(bonus_words(s, vocab))}")
            if unknown:
                bad += 1
                print(f"   ✗ not in vocab or BONUS: {' '.join(unknown)}")
    return 1 if bad else 0


if __name__ == "__main__":
    if sys.argv[1:2] == ["check"]:
        sys.exit(_check())
    print(__doc__)
