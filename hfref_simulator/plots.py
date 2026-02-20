import matplotlib.pyplot as plt


def quick_plots(df):
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    axes[0].hist(df["SBP"], bins=20)
    axes[0].set_title("Clinic SBP")
    axes[1].hist(df["HR"], bins=20)
    axes[1].set_title("Clinic HR")
    axes[2].hist(df["TIR_low_sys"], bins=20)
    axes[2].set_title("TIR low SBP (%)")
    fig.tight_layout()
    return fig
