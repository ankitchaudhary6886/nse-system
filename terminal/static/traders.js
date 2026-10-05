// Traders — one section per published book. Every book keeps its OWN methods;
// they are never merged into a single "Trading method".
//
// PAGE SHAPE (Trading methods view -> #tradersIndex):
//   group by pillar (Long-term quality / Short-term swings / Both horizons)
//     -> one card per book (title, author, what the book is about, method count)
//       -> that book's own method list (name + plain-English description)
//
// Every book and every method carries a "?" button that opens the shared
// explanation dialog (#dataDetailDialog / #methodGuideBody), the same dialog
// explainer.js uses.

/* ------------------------------------------------------------------ words --- */

// Plain-English glosses for the short jargon strings that appear inside book
// method names and descriptions. Without this the owner sees "ATR" or "EMA".
var TM_PLAIN = [
  ["EMA", "exponential moving average (an average that leans on the newest days)"],
  ["SMA", "simple moving average (the plain average price over N days)"],
  ["MA", "moving average (the average price over the last N days)"],
  ["ATR", "average true range (the typical daily move in rupees)"],
  ["RSI", "relative strength index (0-100: how stretched the recent moves are)"],
  ["ADX", "average directional index (how strong a trend is, 0-100)"],
  ["MACD", "moving average convergence divergence (a trend-flip indicator)"],
  ["BB", "Bollinger bands (a channel drawn two standard moves around an average price)"],
  ["P/B", "price compared with book value"],
  ["P/E", "price compared with yearly profit"],
  ["P/CF", "price compared with cash the business generates"],
  ["PSR", "price compared with yearly sales"],
  ["PE", "price compared with yearly profit"],
  ["PB", "price compared with book value"],
  ["RS", "relative strength (how the stock has done against the rest of the market)"],
  ["S/R", "support and resistance (prices where buyers or sellers showed up before)"],
  ["R/R", "reward compared with risk"],
  ["ROCE", "return on capital employed (profit earned per rupee of capital used)"],
  ["ROE", "return on equity (profit earned per rupee of owners' money)"],
  ["ROA", "return on assets (profit earned per rupee of assets)"],
  ["ROIC", "return on invested capital (profit earned per rupee invested)"],
  ["CFO", "cash from operations (cash the business actually generated)"],
  ["D/E", "debt compared with owners' money"],
  ["EBIT", "operating profit before interest and tax"],
  ["TEV", "total enterprise value (what the whole business is priced at, including debt)"],
  ["EPS", "earnings per share (yearly profit divided by the number of shares)"],
  ["FY", "financial year"],
  ["YoY", "compared with the same period a year ago"],
  ["NCAV", "net current asset value (short-term assets minus all money owed)"],
  ["SAR", "parabolic stop and reverse (a trailing stop line that flips sides)"],
  ["SSTO", "smoothed stochastic (an oscillator that times turning points)"],
  ["FI", "force index (price move multiplied by how much was traded)"],
  ["TLB", "three-line break (a chart that only draws when price breaks a level)"],
  ["SMC", "smart-money concepts (reading institutional footprints on a chart)"],
  ["VCP", "volatility contraction pattern (pullbacks that keep getting shallower)"],
  ["HTF", "high tight flag (a sharp advance, then a tight sideways drift)"],
  ["NSE", "National Stock Exchange"],
  ["Nifty 50", "the 50 largest listed Indian companies, used as the market yardstick"],
  ["Nifty", "the market yardstick of the largest listed Indian companies"],
  ["SAST", "the NSE disclosure of large-shareholder stakes"],
  ["DR-", "a data request still waiting to be filled"],
  ["IBC", "India's insolvency proceedings"],
  ["NCLT", "India's insolvency tribunal"],
  ["RBI", "Reserve Bank of India"],
  ["repo rate", "the RBI's main lending rate"],
  ["TTM", "trailing twelve months (the last four reported quarters)"],
  ["SMA3", "3-day moving average"],
  ["SMA10", "10-day moving average"],
  ["SMA12", "12-day moving average"],
  ["SMA20", "20-day moving average"],
  ["SMA50", "50-day moving average"],
  ["SMA180", "180-day moving average"],
  ["MMA", "moving average"]
];

var TM_GLOSS = {};
TM_PLAIN.forEach(function (pair) { TM_GLOSS[pair[0]] = pair[1]; });

var TM_GLOSS_RE = new RegExp(
  TM_PLAIN.map(function (pair) {
    return pair[0].replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }).join("|"),
  "g"
);

function tmEsc(value) {
  return String(value == null ? "" : value)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// Escape first, then wrap known jargon in a dotted underline carrying the
// plain-English meaning. The short letters stay; the owner can hover or read
// the note. Names are shown as written, so nothing rewrites the book's words.
function tmWords(text) {
  return tmEsc(text).replace(TM_GLOSS_RE, function (hit) {
    return '<span class="tm-jargon" title="' + tmEsc(TM_GLOSS[hit]) + '">' +
      hit + "</span>";
  });
}

// Method directions in this registry are only "long" and "both".
function tmDirection(value) {
  var key = String(value == null ? "" : value).toLowerCase();
  if (key === "long" || key === "bullish") return "Expect a rise";
  if (key === "short" || key === "bearish") return "Expect a fall";
  if (key === "both") return "Works both ways";
  return "Not stated in the book";
}

/* ------------------------------------------------------------- structure --- */

var TM_PILLARS = [
  {
    key: "funda",
    title: "Long-term quality",
    blurb: "Books that pick companies to hold for years. They judge the business " +
      "(profit, debt, price paid) rather than the next few days of price."
  },
  {
    key: "swing",
    title: "Short-term swings",
    blurb: "Books that pick a moment. They judge the chart over days to weeks, " +
      "looking for a price level where a move may start."
  },
  {
    key: "multi",
    title: "Both horizons",
    blurb: "Books that do both. The same author gives some rules for long holds " +
      "and some for short swings, so this book is useful either way."
  }
];

// One plain-language line per book (plus, in the dialog, how the book actually
// chooses). `about` is short enough to sit under the title on the card.
var TM_BOOKS = {
  john_crane: {
    about: "Times a swing with the calendar as well as the chart, so entries land near a turning date.",
    theme: "Crane's idea is that a market move runs for a fairly regular length of time. If you count the days of the last move, you can guess when the next turn is due, then use the chart to confirm it.",
    finds: "Completed counter-trend swings, next reversal dates, retracement zones, gaps, and days that confirm a turn.",
    note: "Every rule here is date-and-price arithmetic on the chart. Nothing waits on company accounts."
  },
  larry_spears: {
    about: "Screens only lively, fast-moving stocks, then waits for a pullback inside an uptrend.",
    theme: "Spears starts from volatility. Only stocks that already move more than the market are worth short-term attention, because a quiet stock cannot pay for the effort.",
    finds: "Stocks that are lively enough, have just gapped or turned, and are lined up correctly on their short averages.",
    note: "The book's stop-loss and position-sizing rules were deliberately left out; those stay the owner's decision."
  },
  oshaughnessy: {
    about: "Ranks the whole market on one simple number, then buys the top of that list each year.",
    theme: "O'Shaughnessy tested single rules (cheap, high dividend, strong price run) over decades of data. The book's point is that a plain rule followed without emotion beats clever timing.",
    finds: "The names that qualify for each annual list: cheapest, highest yielding, best price runners, and the mixtures of those.",
    note: "A name appearing here means \"it belongs on this year's list\". It is not a moment to buy, and no stop or target is given."
  },
  quantitative_value: {
    about: "Throws out unreliable or over-indebted companies first, then buys the cheapest of what is left.",
    theme: "Gray and Carlisle first remove companies that look like frauds, manipulators, or likely to fail, then rank the survivors by how little you pay for each rupee of profit, and prefer financially strong ones among the cheapest.",
    finds: "Cheap profitable companies, balance sheets that are not stretched, and the accounting red flags the book wants removed.",
    note: "Several rules need company accounts we do not store yet (cash flow, total assets, share history). Those sit quiet and will start working when the data arrives."
  },
  value_investing_made_easy: {
    about: "A simple restatement of Graham's rules: buy solid companies well below what they are worth.",
    theme: "This is Graham for a beginner. Price and value are different things; a company is worth roughly its earnings and assets, and you should only buy when the price is well under that, then wait years.",
    finds: "Cheap-but-solid companies, margin-of-safety checks, dividend and balance-sheet tests, and the special situations Graham described.",
    note: "The special-situation methods (mergers, liquidations, distressed bonds) need filing feeds we do not have, so they stay quiet for now."
  },
  way_of_the_turtle: {
    about: "A fully mechanical breakout system: buy when price clears a high, cut losses fast, ride winners.",
    theme: "The Turtles were taught one repeatable recipe. Breakouts start trends, most trades lose a little, and a few big winners pay for everything. No opinion is allowed.",
    finds: "Breakouts above a recent high or an upper channel, filtered by whether the longer trend is up.",
    note: "Stops and position sizing in the book are in units of average daily move. That is trade management, so it is left to the owner."
  },
  seven_simple_strategies: {
    about: "Eleven long-only swing recipes built from breakouts, crossovers, trend lines, and candles.",
    theme: "A practical cookbook: each chapter gives one repeatable swing idea, states exactly what to look for on the chart, and nothing more.",
    finds: "Breakouts with volume, crossovers of short and long averages, trend-line and channel touches, and hammer or doji reversal candles.",
    note: "Only the long side was extracted. Intraday and short-selling rules from the book were left out by request."
  },
  apurva_parikh: {
    about: "One Indian value checklist: eleven 'secrets' run together as a single filter.",
    theme: "Parikh's eleven secrets are screening habits, not eleven separate strategies. They work as one chain: value, quality, growth, and a check on how much the market is paying overall.",
    finds: "Indian companies passing the combined checklist of valuation, quality, and growth tests.",
    note: "Five of the eleven secrets need data we do not store yet (years of fundamentals, promoter pledges, market-wide valuation), so the chain currently tests the five that are computable."
  },
  ishaan_agnihotri: {
    about: "Five practical trade setups: reversal at support, pullback in an uptrend, and divergence.",
    theme: "A working trader's playbook. Each setup names the exact chart conditions, the level that must hold, and the volume confirmation needed before it counts.",
    finds: "Trend reversals at a support level, breakouts from a pattern, pullbacks into a rising trend, and price-versus-momentum divergence."
  },
  nison: {
    about: "Candlestick signals used at real support levels, with a reward-versus-risk check.",
    theme: "Nison's contribution is reading one or two candles in context. A hammer alone means little; the same hammer at a level that already held twice is a signal.",
    finds: "Reversal candles at support, rising gaps that later hold as support, tall candle zones, oversold stretches, and candlestick chart tricks (three-line break, Renko, Kagi).",
    note: "One rule overlaps Ishaan Agnihotri's reversal-at-support rule. Both are kept and the overlap is marked, so the owner can decide later."
  },
  chande: {
    about: "A small set of robust trend-following and pullback rules with clear exit triggers.",
    theme: "Chande tests simple ideas honestly. A few consecutive closes beyond a long average, or a breakout followed by a quiet pullback, is enough; the exit rule matters as much as the entry.",
    finds: "Trend starts confirmed by consecutive closes, channel breakouts that pull back, rising trend strength, and washed-out bottoms."
  },
  oneil: {
    about: "Growth-stock bases: cup-with-handle, flat base, high tight flag, plus a market filter.",
    theme: "O'Neil buys companies whose profits are accelerating, only while the chart has built a proper base and only while the overall market is in an uptrend. The market filter is not optional.",
    finds: "Base breakouts on volume, and the market-direction check that decides whether any of them may be acted on.",
    note: "These rules wait on quarterly profit data, a relative-strength rating, and daily index data. Until then they correctly report nothing rather than a guess."
  },
  mcallen: {
    about: "Classic chart and candlestick patterns: bottoms to buy, and top warnings to review.",
    theme: "McAllen collects the standard pattern library and explains what each one means about buyers and sellers. Some patterns mark a low; others warn that a rise is running out of steam.",
    finds: "Saucer and island bottoms, three white soldiers, harami reversals, and seven top-warning patterns such as three black crows and shooting stars.",
    note: "Top warnings are information, not sell orders or bets against the stock. They simply flag a rise that may be tiring."
  },
  singhal: {
    about: "Eighteen ready Indian setups across charts, indicators, gaps, and price patterns.",
    theme: "A wide catalogue of Indian-market setups, written as exact recipes: which indicator, which level, and what must happen before entering.",
    finds: "Band and indicator pullbacks, triangle and squeeze breakouts, Ichimoku and Supertrend trends, sector strength, pin bars, VCP, and two-legged pullbacks.",
    note: "The repo-rate rule stays silent until the RBI rate series is added. Intraday, options, and short-side chapters were left out of this book's extraction."
  }
};

var TM_FALLBACK_BOOK = {
  about: "A published book whose own rules are listed below.",
  theme: "This book's own rules are listed below. They are never mixed with another book's rules.",
  finds: "The conditions this book states, checked against the latest stored prices.",
  note: ""
};

/* ---------------------------------------------------------------- dialog --- */

function tmDialogParts() {
  var dialog = document.getElementById("dataDetailDialog");
  var heading = document.getElementById("dataDetailTitle");
  var body = document.getElementById("dataDetailBody");
  var guide = document.getElementById("methodGuideBody");
  if (!dialog || !heading || !body || !guide) return null;
  return { dialog: dialog, heading: heading, body: body, guide: guide };
}

// Show the guide pane and hide the raw JSON pane. explainer.js does the
// opposite when it renders an explanation, so the two share the dialog safely.
function tmPrepareGuide(parts) {
  parts.body.classList.add("hidden");
  parts.body.style.display = "none";
  parts.guide.replaceChildren();
  parts.guide.classList.remove("hidden");
}

function tmRender(parts, blocks) {
  parts.guide.replaceChildren();
  blocks.forEach(function (block) {
    if (!block || !block.t) return;
    var node;
    if (block.t === "h") {
      node = document.createElement("h3");
      node.textContent = block.text || "";
    } else if (block.t === "p") {
      node = document.createElement("p");
      node.innerHTML = block.html || "";
    } else if (block.t === "warn") {
      node = document.createElement("p");
      node.className = "method-warning";
      node.innerHTML = block.html || "";
    } else if (block.t === "note") {
      node = document.createElement("p");
      node.className = "method-note";
      node.innerHTML = block.html || "";
    } else if (block.t === "field") {
      node = document.createElement("div");
      node.className = "level";
      var label = document.createElement("span");
      label.textContent = block.label || "";
      var value = document.createElement("strong");
      value.innerHTML = block.html || "";
      node.append(label, value);
    } else if (block.t === "list") {
      node = document.createElement("ol");
      (block.items || []).forEach(function (item) {
        var li = document.createElement("li");
        li.textContent = item;
        node.appendChild(li);
      });
    } else {
      return;
    }
    parts.guide.appendChild(node);
  });
  if (!parts.dialog.open) parts.dialog.showModal();
}

function tmOpenBook(book) {
  var parts = tmDialogParts();
  if (!parts) return;
  var info = TM_BOOKS[book.slug] || TM_FALLBACK_BOOK;
  var pill = tmPillar(book.pillar);
  parts.heading.textContent = book.name + " · " + (book.source || "Published book");
  tmPrepareGuide(parts);

  var blocks = [
    { t: "p", html: tmWords(info.about) },
    { t: "h", text: "What this book is about" },
    { t: "p", html: tmWords(info.theme || info.about) },
    { t: "h", text: "What it looks for" },
    { t: "p", html: tmWords(info.finds) },
    {
      t: "field",
      label: "Written by",
      html: tmWords(book.source || "Source not recorded")
    },
    {
      t: "field",
      label: "Methods in this book",
      html: String(book.methods.length) +
        (book.methods.length === 1 ? " method" : " methods")
    },
    { t: "field", label: "Horizon", html: tmEsc(pill.title) }
  ];
  if (info.note) {
    blocks.push({ t: "h", text: "Worth knowing" });
    blocks.push({ t: "p", html: tmWords(info.note) });
  }
  blocks.push({
    t: "list",
    items: [
      "This book's rules are checked only against its own method list. Nothing here is blended with another book.",
      "A method lighting up means its stated conditions match today's stored prices. It is not a recommendation.",
      "Use Check books on a company's research page to see which of these books currently fit that stock."
    ]
  });
  blocks.push({
    t: "warn",
    html: "Research only. A matching rule is not a recommendation and not an order."
  });
  tmRender(parts, blocks);
}

function tmOpenMethod(book, method) {
  var parts = tmDialogParts();
  if (!parts) return;
  var info = TM_BOOKS[book.slug] || TM_FALLBACK_BOOK;
  parts.heading.textContent = book.name + " · " +
    (method.name || method.id || "Method");
  tmPrepareGuide(parts);

  var steps = [
    "Read the book's own rule: " +
      (method.description || "confirm the rule with its source before using it."),
    "Check the stated chart or company conditions against the data currently " +
      "shown for the stock.",
    "Use Check books on the research page to see whether this book currently " +
      "matches that stock.",
    "Before considering any trade, decide the entry, the level that proves the " +
      "idea wrong, how much to risk, and when to exit. Do not invent missing " +
      "levels: some research screens give none on purpose."
  ];

  var blocks = [
    { t: "p", html: tmWords(book.source || "Published book") },
    { t: "p", html: tmWords(method.description ||
      "The registry holds no plain-language description for this method.") },
    { t: "h", text: "How to use it" },
    { t: "list", items: steps },
    { t: "field", label: "Direction", html: tmEsc(tmDirection(method.direction)) },
    { t: "field", label: "From this book", html: tmWords(info.about) }
  ];
  if (info.note) {
    blocks.push({ t: "field", label: "Worth knowing", html: tmWords(info.note) });
  }
  blocks.push({
    t: "warn",
    html: "Research only. A scan match is not a recommendation or an order, " +
      "and no confidence label is a proven win rate."
  });
  tmRender(parts, blocks);
}

/* ----------------------------------------------------------------- index --- */

function tmPillar(key) {
  for (var i = 0; i < TM_PILLARS.length; i += 1) {
    if (TM_PILLARS[i].key === key) return TM_PILLARS[i];
  }
  return {
    key: key || "other",
    title: "Other books",
    blurb: "Books that did not declare a horizon."
  };
}

function tmMethodRow(book, method, index) {
  return '' +
    '<div class="tm-method">' +
      '<div class="tm-method-name">' + tmEsc(method.name || method.id || "Method") +
        '<button type="button" class="tm-help" data-tm-method="' + index +
        '" title="Explain this method in plain words" ' +
        'aria-label="Explain the method ' +
        tmEsc(method.name || method.id || "method") + '">?</button>' +
      '</div>' +
      '<div class="tm-method-desc">' +
        (method.description
          ? tmWords(method.description)
          : "This book states no short description for this rule.") +
      '</div>' +
      '<div class="tm-method-meta">' + tmEsc(tmDirection(method.direction)) + '</div>' +
    '</div>';
}

function tmBookCard(book) {
  var info = TM_BOOKS[book.slug] || TM_FALLBACK_BOOK;
  var count = book.methods.length;
  var html = '' +
    '<div class="tm-book" id="tm-book-' + tmEsc(book.slug) + '">' +
      '<div class="tm-book-head">' +
        '<div class="tm-book-title">' +
          '<h3>' + tmEsc(book.name) + '</h3>' +
          '<button type="button" class="tm-help" data-tm-book="' +
            tmEsc(book.slug) + '" title="Explain this book in plain words" ' +
            'aria-label="Explain the book ' + tmEsc(book.name) + '">?</button>' +
        '</div>' +
        '<p class="tm-book-source">' + tmEsc(book.source || "Source not recorded") + '</p>' +
        '<p class="tm-book-about">' + tmWords(info.about) + '</p>' +
        '<p class="tm-book-count"><span class="badge">' + count +
          (count === 1 ? " method" : " methods") + '</span>' +
          '<span class="tm-count-note">in this book only</span></p>' +
      '</div>' +
      '<div class="tm-methods">' +
        book.methods.map(function (method, index) {
          return tmMethodRow(book, method, index);
        }).join("") +
      '</div>' +
    '</div>';
  return html;
}

function tmPillarSection(pillar, books) {
  var nMethods = books.reduce(function (sum, book) {
    return sum + book.methods.length;
  }, 0);
  return '' +
    '<details class="tm-group" open>' +
      '<summary class="tm-group-head">' +
        '<strong>' + tmEsc(pillar.title) + '</strong>' +
        '<span class="badge">' + books.length +
          (books.length === 1 ? " book" : " books") + ' · ' + nMethods +
          (nMethods === 1 ? " method" : " methods") + '</span>' +
      '</summary>' +
      '<p class="tm-group-blurb">' + tmEsc(pillar.blurb) + '</p>' +
      '<div class="tm-book-list">' +
        books.map(tmBookCard).join("") +
      '</div>' +
    '</details>';
}

function tmWire(container) {
  container.querySelectorAll("[data-tm-method]").forEach(function (button) {
    button.addEventListener("click", function (event) {
      event.preventDefault();
      event.stopPropagation();
      var card = button.closest(".tm-book");
      var book = card && _tradersCache.find(function (item) {
        return item.slug === card.id.replace("tm-book-", "");
      });
      if (!book) return;
      var method = book.methods[Number(button.getAttribute("data-tm-method"))];
      if (method) tmOpenMethod(book, method);
    });
  });
  container.querySelectorAll("[data-tm-book]").forEach(function (button) {
    button.addEventListener("click", function (event) {
      event.preventDefault();
      event.stopPropagation();
      var book = _tradersCache.find(function (item) {
        return item.slug === button.getAttribute("data-tm-book");
      });
      if (book) tmOpenBook(book);
    });
  });
}

async function loadTradersIndex() {
  var box = document.getElementById("tradersIndex");
  if (!box) return;
  var totalBox = document.getElementById("tradersIntroTotal");
  if (totalBox) totalBox.textContent = "";
  box.innerHTML = "<p>Loading the books...</p>";
  var data;
  try {
    data = await api("/api/traders");
  } catch (error) {
    box.replaceChildren();
    var failed = document.createElement("p");
    failed.className = "method-warning";
    failed.textContent =
      "We could not load the book list just now. Please try again in a moment.";
    var why = document.createElement("p");
    why.className = "method-note";
    why.textContent = "Technical detail: " + String(error && error.message || error);
    box.append(failed, why);
    return;
  }

  _tradersCache = (data.traders || []).map(function (book) {
    return {
      slug: book.slug,
      name: book.name,
      pillar: book.pillar,
      source: book.source,
      methods: Array.isArray(book.methods) ? book.methods : []
    };
  });

  if (!_tradersCache.length) {
    box.innerHTML = "<p>No books are registered yet.</p>";
    return;
  }

  // A book with no methods has nothing to show under its own heading.
  var withMethods = _tradersCache.filter(function (book) {
    return book.methods.length > 0;
  });
  if (!withMethods.length) {
    box.innerHTML = "<p>No book methods are registered yet.</p>";
    return;
  }

  var totalMethods = withMethods.reduce(function (sum, book) {
    return sum + book.methods.length;
  }, 0);
  if (totalBox) {
    totalBox.textContent = withMethods.length + " books · " + totalMethods +
      " methods, each belonging to one book.";
  }
  var html = "";
  TM_PILLARS.forEach(function (pillar) {
    var books = withMethods.filter(function (book) {
      return book.pillar === pillar.key;
    });
    if (books.length) html += tmPillarSection(pillar, books);
  });
  var seen = withMethods.filter(function (book) {
    return !TM_PILLARS.some(function (pillar) { return pillar.key === book.pillar; });
  });
  if (seen.length) {
    html += tmPillarSection(
      { title: "Other books", blurb: "Books that did not declare a horizon." },
      seen
    );
  }
  if (data.error) {
    html += '<p class="method-warning">Some books could not be listed just ' +
      "now, so this list may be incomplete.</p>";
  }
  box.innerHTML = html;
  tmWire(box);
}
window.loadTradersIndex = loadTradersIndex;

/* ----------------------------------------------------------------- match --- */

let _matchedSymbol = null;
let _matchRequestId = 0;

function tmNoticeNode(text, detail) {
  const wrapper = document.createElement("div");
  wrapper.className = "tm-notice";
  const line = document.createElement("p");
  line.textContent = text;
  wrapper.appendChild(line);
  if (detail) {
    const meta = document.createElement("p");
    meta.className = "tm-notice-detail";
    meta.textContent = detail;
    wrapper.appendChild(meta);
  }
  return wrapper;
}

// One short human sentence, always carrying the HTTP status when the server
// answered, and the technical detail kept apart. Never a raw error string.
function tmMatchFailure(error) {
  const status = error && error.status;
  if (status === 404) {
    return tmNoticeNode(
      "We could not check the books for this company just now: it is not in our " +
      "stored list of companies.",
      "Technical detail: HTTP 404 · not found."
    );
  }
  if (status >= 400) {
    return tmNoticeNode(
      "We could not check the books for this company just now.",
      "Technical detail: HTTP " + status + ". The book check is on our side and " +
      "does not mean anything is wrong with the company."
    );
  }
  return tmNoticeNode(
    "We could not reach the book check just now, so we have no answer for this " +
    "company yet.",
    "Technical detail: no reply from the server (HTTP status unavailable)."
  );
}

async function tmFetchMatches(symbol) {
  let res;
  try {
    res = await fetch("/api/traders/matches/" + encodeURIComponent(symbol), {
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" }
    });
  } catch (unreachable) {
    const offline = new Error("network");
    offline.status = null;
    throw offline;
  }
  if (!res.ok) {
    const httpError = new Error("HTTP " + res.status);
    httpError.status = res.status;
    throw httpError;
  }
  const payload = await res.json();
  return { data: payload, status: res.status };
}

async function loadTraderMatches(symbol) {
  const box = document.getElementById("traderMatchBox");
  const btn = document.getElementById("refreshTraderMatches");
  if (!box || !symbol) return;
  const requestId = ++_matchRequestId;
  _matchedSymbol = symbol.trim().toUpperCase();
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Checking…";
  }
  box.textContent = "Checking which books fit " + _matchedSymbol + "…";

  let reply = null;
  try {
    reply = await tmFetchMatches(_matchedSymbol);
  } catch (error) {
    if (requestId === _matchRequestId) box.replaceChildren(tmMatchFailure(error));
    if (btn && requestId === _matchRequestId) {
      btn.disabled = !_matchedSymbol;
      btn.textContent = "Check books";
    }
    return;
  }

  if (requestId !== _matchRequestId) return;
  if (btn) {
    btn.disabled = false;
    btn.textContent = "Check books";
  }

  const data = reply.data;
  box.replaceChildren();
  if (data.error) {
    box.appendChild(tmNoticeNode(
      "We could not check the books for this company just now.",
      "Technical detail: HTTP " + (reply.status || 200) +
      ". The server reported a problem while checking the books."
    ));
    return;
  }
  if (!data.in_scan_universe) {
    box.appendChild(tmNoticeNode(
      data.message || "This company is outside the list of companies we check.",
      "Technical detail: HTTP 200 · the company was skipped, not an error."
    ));
    return;
  }

  const nBooks = Number(data.n_traders_checked) || 0;
  const nMatched = Number(data.n_methods_matched) || 0;
  const status = document.createElement("p");
  status.className = "method-note";
  status.textContent = nMatched + (nMatched === 1 ? " rule" : " rules") +
    " matched across " + nBooks + (nBooks === 1 ? " book" : " books") +
    " · prices as of " + (data.as_of || "an unknown date") +
    ". A matching rule is not a chance of winning.";
  box.appendChild(status);

  if (data.errors && data.errors.length) {
    const warning = document.createElement("p");
    warning.className = "method-warning";
    warning.textContent = "Some books could not be checked just now (" +
      data.errors.length + "), so this answer is incomplete.";
    box.appendChild(warning);
  }

  if (!data.matches || !data.matches.length) {
    const empty = document.createElement("p");
    empty.textContent =
      "No book rule matched this company on the latest stored prices.";
    box.appendChild(empty);
    return;
  }

  data.matches.forEach(function (item) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "method-match";
    const title = document.createElement("strong");
    const methodName = item.method && item.method.name
      ? item.method.name
      : "A rule from this book";
    title.textContent = item.trader + " · " + methodName;
    const details = document.createElement("span");
    const description = item.method && item.method.description
      ? item.method.description
      : (item.signal && item.signal.notes) ||
        "Open this rule for what it means and how to use it.";
    details.textContent = description;
    button.append(title, details);
    button.addEventListener("click", function () {
      tmOpenMethod(
        {
          slug: item.slug,
          name: item.trader,
          source: item.source,
          methods: []
        },
        item.method || { name: methodName, description: description }
      );
    });
    box.appendChild(button);
  });
}
window.loadTraderMatches = loadTraderMatches;

document.addEventListener("DOMContentLoaded", function () {
  const btn = document.getElementById("refreshTraderMatches");
  if (btn) {
    btn.addEventListener("click", function () {
      if (_matchedSymbol) loadTraderMatches(_matchedSymbol);
    });
  }
});
