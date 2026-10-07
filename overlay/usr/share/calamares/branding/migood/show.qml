/* Slides shown while Migood OS installs. */
import QtQuick 2.0;
import calamares.slideshow 1.0;

Presentation {
    id: presentation
    function nextSlide() { presentation.goToNextSlide(); }
    Timer { interval: 6000; running: presentation.activatedInCalamares; repeat: true; onTriggered: nextSlide() }

    Repeater {
        model: [
            ["Welcome to Migood OS", "Your games, your friends and Migood AI, built into the computer."],
            ["Sign in once", "After the restart, sign in with Migood Games. That becomes this computer's account and works offline too."],
            ["Play anything", "Migood Games, Steam with Proton, Windows games through Bottles, and Remote Play to your other PCs."],
            ["Always up to date", "Migood Updates gets new versions by itself and keeps a snapshot so nothing breaks."]
        ]
        Slide {
            Rectangle { anchors.fill: parent; color: "#0d141c" }
            Column {
                anchors.centerIn: parent
                spacing: 18
                width: parent.width * 0.8
                Image { source: "migood-button.png"; width: 96; height: 96; anchors.horizontalCenter: parent.horizontalCenter; fillMode: Image.PreserveAspectFit }
                Text { text: modelData[0]; color: "#ffffff"; font.pixelSize: 30; font.bold: true; font.family: "Nunito"; anchors.horizontalCenter: parent.horizontalCenter }
                Text { text: modelData[1]; color: "#b8c2cc"; font.pixelSize: 18; font.family: "Nunito"; wrapMode: Text.WordWrap; width: parent.width; horizontalAlignment: Text.AlignHCenter }
            }
        }
    }
}
