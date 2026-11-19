from kid_assistant import main


def test_main_prints_greeting(capsys):
    main()
    assert "kid-assistant" in capsys.readouterr().out
