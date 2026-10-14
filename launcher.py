import multiprocessing

if __name__ == "__main__":
    multiprocessing.freeze_support()
    from sdr_bridge.app import main
    main()
