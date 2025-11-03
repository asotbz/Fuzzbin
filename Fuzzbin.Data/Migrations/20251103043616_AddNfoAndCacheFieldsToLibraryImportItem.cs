using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Fuzzbin.Data.Migrations
{
    /// <inheritdoc />
    public partial class AddNfoAndCacheFieldsToLibraryImportItem : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<string>(
                name: "CacheMetadataJson",
                table: "LibraryImportItems",
                type: "TEXT",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "FeaturedArtistsJson",
                table: "LibraryImportItems",
                type: "TEXT",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "MetadataSource",
                table: "LibraryImportItems",
                type: "TEXT",
                maxLength: 50,
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "NfoMetadataJson",
                table: "LibraryImportItems",
                type: "TEXT",
                nullable: true);

            migrationBuilder.CreateIndex(
                name: "IX_LibraryImportItems_MetadataSource",
                table: "LibraryImportItems",
                column: "MetadataSource");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropIndex(
                name: "IX_LibraryImportItems_MetadataSource",
                table: "LibraryImportItems");

            migrationBuilder.DropColumn(
                name: "CacheMetadataJson",
                table: "LibraryImportItems");

            migrationBuilder.DropColumn(
                name: "FeaturedArtistsJson",
                table: "LibraryImportItems");

            migrationBuilder.DropColumn(
                name: "MetadataSource",
                table: "LibraryImportItems");

            migrationBuilder.DropColumn(
                name: "NfoMetadataJson",
                table: "LibraryImportItems");
        }
    }
}
