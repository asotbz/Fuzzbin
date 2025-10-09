using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using Refit;

namespace Fuzzbin.Services.External.Imvdb;

public interface IImvdbApi
{
    [Get("/search/videos")]
    Task<ImvdbSearchResponse> SearchVideosAsync(
        [AliasAs("q")] string query,
        [AliasAs("page")] int page = 1,
        [AliasAs("per_page")] int perPage = 20,
        CancellationToken cancellationToken = default);

    [Get("/video/{id}")]
    Task<ImvdbVideoResponse> GetVideoAsync(
        string id,
        CancellationToken cancellationToken = default);
}

public class ImvdbSearchResponse
{
    [AliasAs("results")]
    public List<ImvdbVideoSummary> Results { get; set; } = new();

    [AliasAs("meta")]
    public ImvdbSearchMeta Meta { get; set; } = new();
}

public class ImvdbSearchMeta
{
    [AliasAs("total")]
    public int Total { get; set; }

    [AliasAs("page")]
    public int Page { get; set; }

    [AliasAs("per_page")]
    public int PerPage { get; set; }
}

public class ImvdbVideoSummary
{
    [AliasAs("id")]
    public int Id { get; set; }

    [AliasAs("title")]
    public string? Title { get; set; }

    [AliasAs("song_title")]
    public string? SongTitle { get; set; }

    [AliasAs("artist")]
    public string? Artist { get; set; }

    [AliasAs("image")]
    public string? ImageUrl { get; set; }

    [AliasAs("url")]
    public string? Url { get; set; }
}

public class ImvdbVideoResponse
{
    [AliasAs("id")]
    public int Id { get; set; }

    [AliasAs("title")]
    public string? Title { get; set; }

    [AliasAs("song_title")]
    public string? SongTitle { get; set; }

    [AliasAs("artist")]
    public string? Artist { get; set; }

    [AliasAs("description")]
    public string? Description { get; set; }

    [AliasAs("release_date")]
    public string? ReleaseDate { get; set; }

    [AliasAs("thumbnail_url")]
    public string? ThumbnailUrl { get; set; }

    [AliasAs("imvdb_url")]
    public string? ImvdbUrl { get; set; }

    [AliasAs("explicit")]
    public bool? IsExplicit { get; set; }

    [AliasAs("unofficial")]
    public bool? IsUnofficial { get; set; }

    [AliasAs("genres")]
    public List<ImvdbGenre> Genres { get; set; } = new();

    [AliasAs("credits")]
    public List<ImvdbCredit> Credits { get; set; } = new();
}

public class ImvdbGenre
{
    [AliasAs("name")]
    public string? Name { get; set; }
}

public class ImvdbCredit
{
    [AliasAs("role")]
    public string? Role { get; set; }

    [AliasAs("person")]
    public ImvdbPerson? Person { get; set; }
}

public class ImvdbPerson
{
    [AliasAs("name")]
    public string? Name { get; set; }
}
