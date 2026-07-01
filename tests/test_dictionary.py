from stock_news_bot.analysis.dictionary import StockDictionary, StockEntry, count_industry_terms


def test_stock_dictionary_merges_aliases_without_overlap():
    dictionary = StockDictionary(
        [
            StockEntry(
                ticker="2330",
                name="台積電",
                aliases=("2330", "台積電", "台積", "TSMC"),
                industry="半導體",
            )
        ]
    )

    mentions = dictionary.match("台積電與TSMC今天被提到，2330也在新聞中。")

    assert mentions["2330"].count == 3
    assert mentions["2330"].label == "台積電(2330)"


def test_count_industry_terms():
    mentions = count_industry_terms("AI伺服器帶動散熱與高速傳輸需求。", {"AI伺服器": ["AI伺服器", "散熱", "高速傳輸"]})

    assert mentions["AI伺服器"].count == 3
