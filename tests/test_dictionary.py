from stock_news_bot.analysis.dictionary import StockDictionary, StockEntry, count_industry_terms


def test_stock_dictionary_merges_aliases_without_overlap():
    dictionary = StockDictionary(
        [
            StockEntry(
                ticker="2330",
                name="台積電",
                short_name="台積電",
                aliases=("2330", "台積電", "台積", "TSMC"),
                industry="半導體",
                market="上市",
            )
        ]
    )

    mentions = dictionary.match("台積電與TSMC今天被提到，2330也在新聞中。")

    assert mentions["2330"].count == 3
    assert mentions["2330"].label == "台積電(2330)"


def test_stock_dictionary_from_full_csv_style_uses_short_name_for_label(tmp_path):
    csv_path = tmp_path / "stocks.csv"
    csv_path.write_text(
        "\n".join(
            [
                "ticker,name,short_name,aliases,industry,market",
                "2330,台灣積體電路製造股份有限公司,台積電,TSMC|Taiwan Semiconductor,半導體,上市",
            ]
        ),
        encoding="utf-8",
    )

    dictionary = StockDictionary.from_csv(csv_path)
    mentions = dictionary.match("今天台積電與TSMC都很熱門。")

    assert dictionary.get("2330").name == "台灣積體電路製造股份有限公司"
    assert dictionary.get("2330").short_name == "台積電"
    assert dictionary.get("2330").market == "上市"
    assert mentions["2330"].label == "台積電(2330)"


def test_count_industry_terms():
    mentions = count_industry_terms("AI伺服器帶動散熱與高速傳輸需求。", {"AI伺服器": ["AI伺服器", "散熱", "高速傳輸"]})

    assert mentions["AI伺服器"].count == 3
