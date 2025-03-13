import discord

class TicTacToeButton(discord.ui.Button):
    def __init__(self, x: int, y: int, label: str):
        self.x = x
        self.y = y
        super().__init__(label=label, row=self.x)

    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None
        self.disabled = True

        match self.view.turn:
            case "X":
                self.style = discord.ButtonStyle.red
                self.label = self.view.turn
                self.view.turn = "O"
                self.view.player = self.view.player2
                self.view.board[self.x][self.y] = self.view.X
            case _:
                self.style = discord.ButtonStyle.green
                self.label = self.view.turn
                self.view.turn = "X"
                self.view.player = self.view.player1
                self.view.board[self.x][self.y] = self.view.O

        if winner := self.view.check_winner():
            self.view.stop()
            match winner:
                case self.view.X:
                    await interaction.client.db.execute("""INSERT INTO tictactoe (user_id, wins) VALUES($1, $2) ON CONFLICT(user_id) DO UPDATE SET wins = tictactoe.wins + excluded.wins""", self.view.player1.id, 1)
                    await interaction.client.db.execute("""INSERT INTO tictactoe (user_id, losses) VALUES($1, $2) ON CONFLICT(user_id) DO UPDATE SET losses = tictactoe.losses + excluded.losses""", self.view.player2.id, 1)
                    return await interaction.response.edit_message(
                        content=f"{self.view.player1.mention} Won the game!",
                        view=self.view,
                        allowed_mentions=discord.AllowedMentions.none(),
                    )

                case self.view.O:
                    await interaction.client.db.execute("""INSERT INTO tictactoe (user_id, wins) VALUES($1, $2) ON CONFLICT(user_id) DO UPDATE SET wins = tictactoe.wins + excluded.wins""", self.view.player2.id, 1)
                    await interaction.client.db.execute("""INSERT INTO tictactoe (user_id, losses) VALUES($1, $2) ON CONFLICT(user_id) DO UPDATE SET losses = tictactoe.losses + excluded.losses""", self.view.player1.id, 1)
                    return await interaction.response.edit_message(
                        content=f"{self.view.player2.mention} Won the game!",
                        view=self.view,
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
                case _:
                    await interaction.client.db.execute("""INSERT INTO tictactoe (user_id, ties) VALUES($1, $2) ON CONFLICT(user_id) DO UPDATE SET ties = tictactoe.ties + excluded.ties""", self.view.player1.id, 1)
                    await interaction.client.db.execute("""INSERT INTO tictactoe (user_id, ties) VALUES($1, $2) ON CONFLICT(user_id) DO UPDATE SET ties = tictactoe.ties + excluded.ties""", self.view.player2.id, 1)
                    return await interaction.response.edit_message(
                        content="It's a tie", view=self.view
                    )

        content = (
            f"⭕ {self.view.player1.mention}, your turn"
            if self.view.turn == "X"
            else f"⭕ {self.view.player2.mention}, your turn"
        )
        return await interaction.response.edit_message(
            content=content,
            view=self.view,
            allowed_mentions=discord.AllowedMentions.none(),
        )