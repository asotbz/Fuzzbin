using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Fuzzbin.Data.Migrations
{
    /// <inheritdoc />
    public partial class AddPerformanceIndexes : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateIndex(
                name: "IX_Videos_CreatedAt",
                table: "Videos",
                column: "CreatedAt");

            migrationBuilder.CreateIndex(
                name: "IX_Videos_Duration",
                table: "Videos",
                column: "Duration");

            migrationBuilder.CreateIndex(
                name: "IX_Videos_LastPlayedAt",
                table: "Videos",
                column: "LastPlayedAt");

            migrationBuilder.CreateIndex(
                name: "IX_Videos_PlayCount",
                table: "Videos",
                column: "PlayCount");

            migrationBuilder.CreateIndex(
                name: "IX_Videos_Rating",
                table: "Videos",
                column: "Rating");

            migrationBuilder.CreateIndex(
                name: "IX_Videos_UpdatedAt",
                table: "Videos",
                column: "UpdatedAt");

            migrationBuilder.CreateIndex(
                name: "IX_Videos_Year",
                table: "Videos",
                column: "Year");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropIndex(
                name: "IX_Videos_CreatedAt",
                table: "Videos");

            migrationBuilder.DropIndex(
                name: "IX_Videos_Duration",
                table: "Videos");

            migrationBuilder.DropIndex(
                name: "IX_Videos_LastPlayedAt",
                table: "Videos");

            migrationBuilder.DropIndex(
                name: "IX_Videos_PlayCount",
                table: "Videos");

            migrationBuilder.DropIndex(
                name: "IX_Videos_Rating",
                table: "Videos");

            migrationBuilder.DropIndex(
                name: "IX_Videos_UpdatedAt",
                table: "Videos");

            migrationBuilder.DropIndex(
                name: "IX_Videos_Year",
                table: "Videos");
        }
    }
}
